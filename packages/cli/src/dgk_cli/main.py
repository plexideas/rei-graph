import click

from dgk_cli.commands.delete_project import delete_project
from dgk_cli.commands.dev import dev
from dgk_cli.commands.doctor import doctor
from dgk_cli.commands.impact import impact
from dgk_cli.commands.init import init
from dgk_cli.commands.mcp import mcp_command
from dgk_cli.commands.plan import plan, plans
from dgk_cli.commands.query import query
from dgk_cli.commands.scan import scan
from dgk_cli.commands.snapshot import snapshot


@click.group()
def cli():
    """dev-graph-kit: Local graph memory for coding agents."""
    pass


cli.add_command(init)
cli.add_command(dev)
cli.add_command(doctor)
cli.add_command(scan)
cli.add_command(snapshot)
cli.add_command(query)
cli.add_command(impact)
cli.add_command(plan)
cli.add_command(plans)
cli.add_command(mcp_command, name="mcp")
cli.add_command(delete_project)
