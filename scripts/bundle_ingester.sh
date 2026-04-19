#!/usr/bin/env bash
# Bundle the compiled TS ingester into the rei-cli package data directory.
#
# Usage:
#   ./scripts/bundle_ingester.sh
#
# This script must be run before `uv build` to produce a wheel that includes
# the pre-compiled ingester.  In CI the release workflow calls it automatically.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INGESTER_DIR="${REPO_ROOT}/packages/ingester_ts"
DEST_DIR="${REPO_ROOT}/packages/cli/src/rei_cli/_ingester"

echo "Building TS ingester..."
cd "${INGESTER_DIR}"
npm ci --silent
npm run build

echo "Copying bundled output to ${DEST_DIR}..."
rm -rf "${DEST_DIR}"
mkdir -p "${DEST_DIR}"
cp dist/cli.js "${DEST_DIR}/"

echo "Done. Bundled ingester is at ${DEST_DIR}/"
