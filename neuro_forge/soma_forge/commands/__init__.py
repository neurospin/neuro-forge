import click

from rich.console import Console
import rich.traceback

rich.traceback.install()

console = Console()


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def cli():
    pass


from . import init
from . import packaging_plan
from . import apply_plan
