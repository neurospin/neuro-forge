import click

from rich.console import Console
import rich.traceback

rich.traceback.install()

console = Console()


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def cli():
    pass


from . import apply_plan
from . import check_merge
from . import graphviz
from . import init
from . import packaging_plan
