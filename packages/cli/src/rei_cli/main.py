import importlib.metadata

import click

from rei_cli.commands.delete_project import delete_project
from rei_cli.commands.doctor import doctor
from rei_cli.commands.service import service
from rei_cli.commands.impact import impact
from rei_cli.commands.init import init
from rei_cli.commands.mcp import mcp_command
from rei_cli.commands.plan import plan, plans
from rei_cli.commands.query import query
from rei_cli.commands.scan import scan
from rei_cli.commands.snapshot import snapshot
from rei_cli.commands.update import update


@click.group()
@click.version_option(
    version=importlib.metadata.version("rei-cli"),
    prog_name="rei",
)
def cli():
    """rei-graph: Local graph memory for coding agents."""
    pass


cli.add_command(init)
cli.add_command(service)
cli.add_command(doctor)
cli.add_command(scan)
cli.add_command(snapshot)
cli.add_command(query)
cli.add_command(impact)
cli.add_command(plan)
cli.add_command(plans)
cli.add_command(mcp_command, name="mcp")
cli.add_command(delete_project)
cli.add_command(update)
