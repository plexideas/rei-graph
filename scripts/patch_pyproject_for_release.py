"""Patch packages/cli/pyproject.toml for a standalone release build.

Replaces workspace path-dependencies with concrete PyPI version ranges, and
expands the hatch wheel target to include the bundled sub-packages.
Called by .github/workflows/release.yml before uv build.
"""
import re
import pathlib

p = pathlib.Path("packages/cli/pyproject.toml")
txt = p.read_text()

# Replace dependencies list with pinned PyPI equivalents
txt = re.sub(
    r'dependencies = \[.*?\]',
    'dependencies = ["click>=8.0", "rich>=13.0", "tomli-w>=1.0", "pydantic>=2.0", "neo4j>=5.0", "mcp>=1.0"]',
    txt,
    flags=re.DOTALL,
)

# Expand hatch wheel packages to include the bundled sub-packages
txt = re.sub(
    r'packages = \["src/rei_cli"\]',
    'packages = ["src/rei_cli", "src/rei_core", "src/rei_storage", "src/rei_mcp"]',
    txt,
)

# Remove [tool.uv.sources] block (not needed for the standalone build)
txt = re.sub(r'\[tool\.uv\.sources\][\s\S]*', '', txt).rstrip() + '\n'

p.write_text(txt)
print(p.read_text())
