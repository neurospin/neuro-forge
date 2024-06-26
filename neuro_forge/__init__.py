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
@click.argument("packages", type=str, nargs=-1)
def build(channel_dir, packages):
    """Create packages with rattler-build for recipes embedded in neuro-forge
    without leaving any cache file in user environment. All temporary files are
    stored (and removed if operation is successful) in CHANNEL_DIR directory.


    CHANNEL_DIR directory where packages are going to be created

    PACKAGES    list of packages to generate (by default all the ones 
                that are not already in the channel)
    """
    # Create an empty channel
    channel_dir = Path(channel_dir).absolute()

    # Make sure channel_dir can be used as a channel
    channel_dir.mkdir(exist_ok=True)
    (channel_dir / "noarch").mkdir(exist_ok=True)
    (channel_dir / "linux-64").mkdir(exist_ok=True)
    check_call(["conda", "index", channel_dir])

    # Select packages
    neuro_forge = Path(__file__).parent.parent
    if not packages:
        packages = [i.name for i in (neuro_forge / "recipes").iterdir() if (i / "recipe.yaml").exists() and not any(channel_dir.glob(f"*/{i.name}-*.conda"))]
    
    # Create selected packages
    for package in packages:
        recipe_file = neuro_forge / "recipes" / package / "recipe.yaml"
        if not recipe_file.exists():
            raise ValueError(f'Wrong package name "{package}": file {recipe_file} does not exist')
        recipe_dir = recipe_file.parent
        command = [
            "env",
            f"HOME={channel_dir}",
            "rattler-build",
            "build",
            "-r",
            str(recipe_dir),
            "--output-dir",
            str(channel_dir),
            "--experimental",
            "-c", "conda-forge",
            "-c", "bioconda"
        ]
        variants = recipe_dir / "variants.yaml"
        if variants.exists():
            command.extend(["-m", str(variants)])
        print("#----------------- calling ------------------------------")
        print(' '.join(f"'{i}'" for i in command))
        print("#--------------------------------------------------------")
        check_call(command)
        

    # Cleanup and create channel index
    check_call(["conda", "index", channel_dir])
    to_delete = [channel_dir / i for i in ("bld", "src_cache", ".rattler", ".cache")]
    to_delete.extend(channel_dir.glob("*/.cache"))
    for i in to_delete:
        if i.exists():
            shutil.rmtree(i)
