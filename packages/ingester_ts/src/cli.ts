#!/usr/bin/env node

import { parseFile } from "./parser.js";
import * as path from "path";

const filePath = process.argv[2];

if (!filePath) {
  console.error("Usage: dgk-parse-ts <file>");
  process.exit(1);
}

const absolutePath = path.resolve(filePath);

try {
  const result = parseFile(absolutePath);
  console.log(JSON.stringify(result));
} catch (error: unknown) {
  const message = error instanceof Error ? error.message : String(error);
  console.error(`Error parsing ${filePath}: ${message}`);
  process.exit(1);
}
