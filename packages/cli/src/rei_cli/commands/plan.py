import click

from pathlib import Path

from rei_core.config import read_config
from rei_storage.dag_client import DagClient


def _resolve_project_id() -> str | None:
    """Read project_id from .rei/project.toml in cwd, or return None."""
    config_path = Path.cwd() / ".rei" / "project.toml"
    if config_path.exists():
        config = read_config(config_path)
        return config.get("project", {}).get("id")
    return None


@click.command()
@click.argument("goal")
@click.argument("steps", nargs=-1, required=True)
def plan(goal: str, steps: tuple[str, ...]):
    """Create a new execution plan: rei plan <goal> <step1> [step2 ...]"""
    project_id = _resolve_project_id()
    dag = DagClient(project_id=project_id)
    try:
        plan_id = dag.create_plan(goal=goal, steps=list(steps))
    finally:
        dag.close()
    click.echo(f"Created plan: {plan_id}")


@click.command()
def plans():
    """List open (pending/running) execution plans."""
    project_id = _resolve_project_id()
    dag = DagClient(project_id=project_id)
    try:
        open_plans = dag.list_open_plans()
    finally:
        dag.close()

    if not open_plans:
        click.echo("No open plans.")
        return

    click.echo(f"{len(open_plans)} open plan(s):\n")
    for p in open_plans:
        click.echo(f"  [{p.get('status', '?')}] {p.get('id', '?')}: {p.get('goal', '')}")
