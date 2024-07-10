import click

from rich.console import Console
import rich.traceback

rich.traceback.install()

@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.pass_context
def cli(context):
    global console

    print("!!!!!!!!!!!!!!!!!!!!!!!!!", context)
    context.console = Console()
    context.console.print("hello")

from . import init
from . import dev_packages_plan