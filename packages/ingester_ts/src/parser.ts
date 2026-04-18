import { Project, SourceFile, SyntaxKind, Node as TSNode } from "ts-morph";
import * as path from "path";
import * as fs from "fs";

export interface GraphNode {
  id: string;
  label: string;
  name: string;
  path: string;
  line: number;
  properties: Record<string, unknown>;
}

export interface GraphRelationship {
  type: string;
  sourceId: string;
  targetId: string;
  properties: Record<string, unknown>;
}

export interface ScanResult {
  file: string;
  nodes: GraphNode[];
  relationships: GraphRelationship[];
}

function makeId(label: string, filePath: string, name?: string, projectPrefix?: string): string {
  const prefix = projectPrefix ? `${projectPrefix}:` : "";
  if (name) {
    return `${label.toLowerCase()}:${prefix}${filePath}:${name}`;
  }
  return `${label.toLowerCase()}:${prefix}${filePath}`;
}

function isReactComponent(name: string): boolean {
  return /^[A-Z]/.test(name);
}

function isReactHook(name: string): boolean {
  return /^use[A-Z]/.test(name);
}

const TS_EXTENSIONS = [".ts", ".tsx", ".js", ".jsx"];

function resolveRelativeImport(sourceFilePath: string, specifier: string): string {
  if (!specifier.startsWith(".")) {
    return specifier; // External package, keep as-is
  }

  const sourceDir = path.dirname(sourceFilePath);
  const resolved = path.resolve(sourceDir, specifier);

  // Try direct file with extensions
  for (const ext of TS_EXTENSIONS) {
    if (fs.existsSync(resolved + ext)) {
      return path.relative(process.cwd(), resolved + ext).replace(/\\/g, "/");
    }
  }

  // Try index files in directory
  for (const ext of TS_EXTENSIONS) {
    const indexPath = path.join(resolved, `index${ext}`);
    if (fs.existsSync(indexPath)) {
      return path.relative(process.cwd(), indexPath).replace(/\\/g, "/");
    }
  }

  // Fallback: return resolved path without extension
  return path.relative(process.cwd(), resolved).replace(/\\/g, "/");
}

export function parseFile(filePath: string, projectPrefix?: string): ScanResult {
  const project = new Project({ compilerOptions: { allowJs: true, jsx: 1 } });
  const sourceFile = project.addSourceFileAtPath(filePath);
  const normalizedPath = path.relative(process.cwd(), filePath).replace(/\\/g, "/");

  const nodes: GraphNode[] = [];
  const relationships: GraphRelationship[] = [];

  // Module node for the file itself
  const moduleId = makeId("module", normalizedPath, undefined, projectPrefix);
  nodes.push({
    id: moduleId,
    label: "Module",
    name: path.basename(normalizedPath, path.extname(normalizedPath)),
    path: normalizedPath,
    line: 1,
    properties: {},
  });

  // Function declarations
  for (const fn of sourceFile.getFunctions()) {
    const name = fn.getName();
    if (!name) continue;

    const exported = fn.isExported();
    const isAsync = fn.isAsync();
    let label = "Function";
    if (isReactComponent(name)) label = "Component";
    else if (isReactHook(name)) label = "Hook";

    const nodeId = makeId(label.toLowerCase(), normalizedPath, name, projectPrefix);
    nodes.push({
      id: nodeId,
      label,
      name,
      path: normalizedPath,
      line: fn.getStartLineNumber(),
      properties: { exported, async: isAsync },
    });

    if (exported) {
      relationships.push({
        type: "EXPOSES",
        sourceId: moduleId,
        targetId: nodeId,
        properties: {},
      });
    }
  }

  // Class declarations
  for (const cls of sourceFile.getClasses()) {
    const name = cls.getName();
    if (!name) continue;

    const exported = cls.isExported();
    const nodeId = makeId("class", normalizedPath, name, projectPrefix);
    nodes.push({
      id: nodeId,
      label: "Class",
      name,
      path: normalizedPath,
      line: cls.getStartLineNumber(),
      properties: { exported },
    });

    if (exported) {
      relationships.push({
        type: "EXPOSES",
        sourceId: moduleId,
        targetId: nodeId,
        properties: {},
      });
    }
  }

  // Interface declarations
  for (const iface of sourceFile.getInterfaces()) {
    const name = iface.getName();
    const exported = iface.isExported();
    const nodeId = makeId("interface", normalizedPath, name, projectPrefix);
    nodes.push({
      id: nodeId,
      label: "Interface",
      name,
      path: normalizedPath,
      line: iface.getStartLineNumber(),
      properties: { exported },
    });

    if (exported) {
      relationships.push({
        type: "EXPOSES",
        sourceId: moduleId,
        targetId: nodeId,
        properties: {},
      });
    }
  }

  // Type alias declarations
  for (const typeAlias of sourceFile.getTypeAliases()) {
    const name = typeAlias.getName();
    const exported = typeAlias.isExported();
    const nodeId = makeId("type", normalizedPath, name, projectPrefix);
    nodes.push({
      id: nodeId,
      label: "Type",
      name,
      path: normalizedPath,
      line: typeAlias.getStartLineNumber(),
      properties: { exported },
    });

    if (exported) {
      relationships.push({
        type: "EXPOSES",
        sourceId: moduleId,
        targetId: nodeId,
        properties: {},
      });
    }
  }

  // Variable declarations (for arrow function components, hooks, and exported consts)
  for (const varStatement of sourceFile.getVariableStatements()) {
    const exported = varStatement.isExported();
    for (const decl of varStatement.getDeclarations()) {
      const name = decl.getName();
      const initializer = decl.getInitializer();

      // Check if it's an arrow function or function expression
      if (
        initializer &&
        (TSNode.isArrowFunction(initializer) || TSNode.isFunctionExpression(initializer))
      ) {
        let label = "Function";
        if (isReactComponent(name)) label = "Component";
        else if (isReactHook(name)) label = "Hook";

        const nodeId = makeId(label.toLowerCase(), normalizedPath, name, projectPrefix);
        nodes.push({
          id: nodeId,
          label,
          name,
          path: normalizedPath,
          line: varStatement.getStartLineNumber(),
          properties: { exported, async: initializer.isAsync() },
        });

        if (exported) {
          relationships.push({
            type: "EXPOSES",
            sourceId: moduleId,
            targetId: nodeId,
            properties: {},
          });
        }
      }
    }
  }

  // Import declarations
  for (const imp of sourceFile.getImportDeclarations()) {
    const moduleSpecifier = imp.getModuleSpecifierValue();
    const resolvedTarget = resolveRelativeImport(filePath, moduleSpecifier);
    const targetModuleId = makeId("module", resolvedTarget, undefined, projectPrefix);

    const namedImports = imp.getNamedImports().map((n) => n.getName());
    const defaultImport = imp.getDefaultImport()?.getText();
    const namespaceImport = imp.getNamespaceImport()?.getText();

    const specifiers: string[] = [];
    if (defaultImport) specifiers.push(defaultImport);
    if (namespaceImport) specifiers.push(`* as ${namespaceImport}`);
    specifiers.push(...namedImports);

    relationships.push({
      type: "IMPORTS",
      sourceId: moduleId,
      targetId: targetModuleId,
      properties: { specifiers, moduleSpecifier },
    });

    // For external packages, create a Package node and DEPENDS_ON relationship
    if (!moduleSpecifier.startsWith(".")) {
      const packageName = moduleSpecifier.startsWith("@")
        ? moduleSpecifier.split("/").slice(0, 2).join("/")
        : moduleSpecifier.split("/")[0];

      const packageId = makeId("package", packageName, undefined, projectPrefix);

      // Only add the package node if we haven't seen it yet
      if (!nodes.some((n) => n.id === packageId)) {
        nodes.push({
          id: packageId,
          label: "Package",
          name: packageName,
          path: "",
          line: 0,
          properties: { external: true },
        });
      }

      relationships.push({
        type: "DEPENDS_ON",
        sourceId: moduleId,
        targetId: packageId,
        properties: {},
      });
    }
  }

  return { file: normalizedPath, nodes, relationships };
}
