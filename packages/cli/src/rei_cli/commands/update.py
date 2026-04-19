import importlib.metadata
import shutil
import subprocess

import click


def _detect_install_method() -> str:
    """Detect how rei-graph was installed.

    Returns one of: ``"brew"``, ``"pipx"``, or ``"unknown"``.
    """
    rei_path = shutil.which("rei")
    if not rei_path:
        return "unknown"

    path_lower = rei_path.lower()
    if "homebrew" in path_lower or "linuxbrew" in path_lower or "/cellar/" in path_lower:
        return "brew"
    if "pipx" in path_lower:
        return "pipx"
    return "unknown"


@click.command()
def update():
    """Update rei-graph to the latest version."""
    current_version = importlib.metadata.version("rei-cli")
    click.echo(f"Updating rei (current version: {current_version})...")

    method = _detect_install_method()

    if method == "brew":
        cmd = ["brew", "upgrade", "rei-graph"]
    elif method == "pipx":
        cmd = ["pipx", "upgrade", "rei-graph"]
    else:
        click.echo(
            "Could not detect install method.\n"
            "To update manually:\n"
            "  brew upgrade rei-graph       (if installed via Homebrew)\n"
            "  pipx upgrade rei-graph       (if installed via pipx)"
        )
        return

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.stdout:
        click.echo(result.stdout.rstrip())
    if result.stderr:
        click.echo(result.stderr.rstrip())

    if result.returncode != 0:
        click.echo(
            f"Update failed (exit code {result.returncode}). "
            "Check the output above for details.",
            err=True,
        )
        raise SystemExit(result.returncode)

    click.echo("Update complete.")
