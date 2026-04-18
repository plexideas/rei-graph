import click

from dgk_storage.dag_client import DagClient


@click.command()
@click.argument("goal")
@click.argument("steps", nargs=-1, required=True)
def plan(goal: str, steps: tuple[str, ...]):
    """Create a new execution plan: dgk plan <goal> <step1> [step2 ...]"""
    dag = DagClient()
    try:
        plan_id = dag.create_plan(goal=goal, steps=list(steps))
    finally:
        dag.close()
    click.echo(f"Created plan: {plan_id}")


@click.command()
def plans():
    """List open (pending/running) execution plans."""
    dag = DagClient()
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
