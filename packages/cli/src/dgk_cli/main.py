import click

from dgk_cli.commands.dev import dev
from dgk_cli.commands.doctor import doctor
from dgk_cli.commands.impact import impact
from dgk_cli.commands.init import init
from dgk_cli.commands.query import query
from dgk_cli.commands.scan import scan


@click.group()
def cli():
    """dev-graph-kit: Local graph memory for coding agents."""
    pass


cli.add_command(init)
cli.add_command(dev)
cli.add_command(doctor)
cli.add_command(scan)
cli.add_command(query)
cli.add_command(impact)
