#!/usr/bin/env python

import click
from itertools import chain
from pathlib import Path
import shutil
from subprocess import check_call


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def main():
    pass


@main.command()
@click.argument("channel_dir", type=click.Path())
def init(channel_dir):
    """Initialise a new channel directory

    CHANNEL_DIR directory where packages are going to be created
    """
    # Create an empty channel
    channel_dir = Path(channel_dir).absolute()
    if not channel_dir.exists():
        check_call(
            [
                "datalad",
                "create",
                "--description",
                "Neuro-forge channel : https://brainvisa.info/neuro-forge",
                str(channel_dir),
            ]
        )
        save_datalad = True
    else:
        save_datalad = False
    (channel_dir / "noarch").mkdir(exist_ok=True)
    (channel_dir / "linux-64").mkdir(exist_ok=True)
    check_call(["conda", "index", channel_dir])

    # Create base packages
    neuro_forge = Path(__file__).parent.parent
    for recipe_dir in chain(
        [neuro_forge / "soma-forge"], (neuro_forge / "recipes").iterdir()
    ):
        if not (recipe_dir / "recipe.yaml").exists():
            continue
        command = [
            "env",
            f"HOME={channel_dir}",
            "rattler-build",
            "build",
            "-r",
            str(recipe_dir),
            "--output-dir",
            str(channel_dir),
        ]
        variants = recipe_dir / "variants.yaml"
        if variants.exists():
            command.extend(["-m", str(variants)])
        check_call(command)
        

    # Cleanup and create channel index
    check_call(["conda", "index", channel_dir])
    to_delete = [channel_dir / i for i in ("bld", "src_cache", ".rattler", ".cache")]
    to_delete.extend(channel_dir.glob("*/.cache"))
    for i in to_delete:
        if i.exists():
            shutil.rmtree(i)
    if save_datalad:
        check_call(
            ["datalad", "save", "-m", "Created initial packages", str(channel_dir)]
        )