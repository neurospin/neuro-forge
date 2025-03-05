import click
import rich.traceback
from rich.console import Console

rich.traceback.install()

console = Console()


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def cli():
    pass


from . import apply_plan, check_merge, graphviz, init, packaging_plan
