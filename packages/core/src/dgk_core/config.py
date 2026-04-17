from pathlib import Path

import tomli_w


DEFAULT_CONFIG = {
    "project": {
        "name": "",
        "language": "typescript",
        "root": ".",
    },
    "scan": {
        "include": ["src", "packages", "apps"],
        "exclude": ["dist", "build", "node_modules", ".next"],
    },
    "memory": {
        "enabled": True,
        "scope": "project",
    },
    "dag": {
        "engine": "dagster",
    },
    "graph": {
        "backend": "neo4j",
    },
}


def generate_default_config(project_name: str) -> dict:
    config = DEFAULT_CONFIG.copy()
    config["project"] = {**config["project"], "name": project_name}
    return config


def write_config(path: Path, config: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        tomli_w.dump(config, f)


def read_config(path: Path) -> dict:
    import tomllib

    with open(path, "rb") as f:
        return tomllib.load(f)
