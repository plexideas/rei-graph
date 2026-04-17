import { Project, SourceFile, SyntaxKind, Node as TSNode } from "ts-morph";
import * as path from "path";

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

function makeId(label: string, filePath: string, name?: string): string {
  if (name) {
    return `${label.toLowerCase()}:${filePath}:${name}`;
  }
  return `${label.toLowerCase()}:${filePath}`;
}

function isReactComponent(name: string): boolean {
  return /^[A-Z]/.test(name);
}

function isReactHook(name: string): boolean {
  return /^use[A-Z]/.test(name);
}

export function parseFile(filePath: string): ScanResult {
  const project = new Project({ compilerOptions: { allowJs: true, jsx: 1 } });
  const sourceFile = project.addSourceFileAtPath(filePath);
  const normalizedPath = path.relative(process.cwd(), filePath).replace(/\\/g, "/");

  const nodes: GraphNode[] = [];
  const relationships: GraphRelationship[] = [];

  // Module node for the file itself
  const moduleId = makeId("module", normalizedPath);
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

    const nodeId = makeId(label.toLowerCase(), normalizedPath, name);
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
    const nodeId = makeId("class", normalizedPath, name);
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
    const nodeId = makeId("interface", normalizedPath, name);
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
    const nodeId = makeId("type", normalizedPath, name);
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

        const nodeId = makeId(label.toLowerCase(), normalizedPath, name);
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
    const targetModuleId = makeId("module", moduleSpecifier);

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
  }

  return { file: normalizedPath, nodes, relationships };
}
