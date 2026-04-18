#!/usr/bin/env node

import { parseFile } from "./parser.js";
import * as path from "path";

// Parse CLI arguments: <file> [--project-prefix <hash>]
const args = process.argv.slice(2);
let filePath: string | undefined;
let projectPrefix: string | undefined;

for (let i = 0; i < args.length; i++) {
  if (args[i] === "--project-prefix" && i + 1 < args.length) {
    projectPrefix = args[++i];
  } else if (!filePath) {
    filePath = args[i];
  }
}

if (!filePath) {
  console.error("Usage: dgk-parse-ts <file> [--project-prefix <hash>]");
  process.exit(1);
}

const absolutePath = path.resolve(filePath);

try {
  const result = parseFile(absolutePath, projectPrefix);
  console.log(JSON.stringify(result));
} catch (error: unknown) {
  const message = error instanceof Error ? error.message : String(error);
  console.error(`Error parsing ${filePath}: ${message}`);
  process.exit(1);
}
