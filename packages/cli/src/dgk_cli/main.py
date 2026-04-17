import click

from dgk_cli.commands.dev import dev
from dgk_cli.commands.doctor import doctor
from dgk_cli.commands.init import init


@click.group()
def cli():
    """dev-graph-kit: Local graph memory for coding agents."""
    pass


cli.add_command(init)
cli.add_command(dev)
cli.add_command(doctor)
