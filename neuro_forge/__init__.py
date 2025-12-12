import click
import functools
import json
import operator
import os
from pathlib import Path
import shutil
import subprocess
import sys
import yaml

default_channel_dir = "/drf/neuro-forge/public"
default_recipes_dir = "/drf/neuro-forge/recipes"


def find_neuro_forge_packages(recipes_dir=default_recipes_dir):
    neuro_forge = Path(__file__).parent.parent
    recipes_dir = Path(recipes_dir)
    if recipes_dir.exists():
        yield from (
            i.name for i in recipes_dir.iterdir() if (i / "recipe.yaml").exists()
        )
    yield from (
        i.name
        for i in (neuro_forge / "recipes").iterdir()
        if (i / "recipe.yaml").exists()
    )


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
    subprocess.check_call(["rattler-index", "fs", channel_dir])

    # Select packages
    neuro_forge = Path(__file__).parent.parent
    if not packages:
        # Select packages for automatic building
        packages = []
        for i in (neuro_forge / "recipes").iterdir():
            if (i / "recipe.yaml").exists():
                existing = list(channel_dir.glob(f"*/{i.name}-*.conda"))
                if existing:
                    print(f"Skip {i} because {existing[0]} exists")
                    continue
                with open(i / "recipe.yaml") as f:
                    recipe = yaml.safe_load(f)
                if not recipe.get("extra", {}).get("neuro-forge", {}).get("exclude"):
                    packages.append(i.name)

    # Create selected packages
    for package in packages:
        recipe_file = neuro_forge / "recipes" / package / "recipe.yaml"
        if not recipe_file.exists():
            raise ValueError(
                f'Wrong package name "{package}": file {recipe_file} does not exist'
            )
        recipe_dir = recipe_file.parent
        extension_file = recipe_dir / "neuro-forge.yaml"
        channels = ["conda-forge", "bioconda"]
        if extension_file.exists():
            with open(extension_file) as f:
                extension = yaml.safe_load(f)
            channels = extension.get("channels", channels)

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
        ] + functools.reduce(operator.add, (["-c", i] for i in channels))
        variants = recipe_dir / "variants.yaml"
        if variants.exists():
            command.extend(["-m", str(variants)])
        print("#----------------- calling ------------------------------")
        print(" ".join(f"'{i}'" for i in command))
        print("#--------------------------------------------------------")
        if subprocess.call(command):
            print(f"\nERROR: building of package {package} failed", file=sys.stderr)
            sys.exit(1)

    # Cleanup and create channel index
    subprocess.check_call(["rattler-index", "fs", channel_dir, "--force"])
    to_delete = [channel_dir / i for i in ("bld", "src_cache", ".rattler", ".cache")]
    to_delete.extend(channel_dir.glob("*/.cache"))
    for i in to_delete:
        if i.exists():
            shutil.rmtree(i)


@main.command()
def publish():
    """Run rattler-index if necessary and publish channels"""

    pixi_root = Path(os.environ["PIXI_PROJECT_ROOT"])
    with open(pixi_root / "neuro-forge.json") as f:
        neuro_forge_conf = json.load(f)

    for name, info in neuro_forge_conf["publication"].items():
        print("-" * 40)
        print(f"Processing {name}:")
        print("-" * 40)
        channel_dir = info.get("directory")
        if channel_dir:
            # Sort all files by modification date and get the most recent
            to_sort = []
            conda_time = 0
            index_time = None
            for root, _, files in os.walk(channel_dir):
                for file in files:
                    ff = os.path.join(root, file)
                    if ff.endswith(".conda"):
                        conda_time = max(conda_time, os.stat(ff).st_mtime)
                    elif os.path.basename(ff) == 'repodata.json':
                        index_time = os.stat(ff).st_mtime
            if index_time is None or index_time < conda_time:
                command = ["rattler-index", "fs", channel_dir, "--force"]
                print(" ".join(f"'{i}'" for i in command))
                subprocess.check_call(command)

            if "ssh" in info:
                destination = info["ssh"]["destination"]
                directory = info["ssh"]["directory"]

                # On web server, make a copy of the channel directory using hard links
                command = [
                    "ssh",
                    f"{destination}",
                    "cp",
                    "-ral",
                    f"{directory}",
                    f"{directory}-update",
                ]
                print(" ".join(f"'{i}'" for i in command))
                subprocess.check_call(command)

                # Update the copy of the channel directory. This can take a while.
                # During the process, the published channel is untouched.
                channel_dir = os.path.normpath(os.path.abspath(channel_dir))
                command = [
                    "rsync",
                    "-r",
                    "--progress",
                    "--delete",
                    "--no-perms",
                    "--times",
                    "--no-owner",
                    "--no-group",
                    "--exclude=.cache",
                    channel_dir + "/",
                    f"{destination}:{directory}-update/neuro-forge/",
                ]
                print(" ".join(f"'{i}'" for i in command))
                subprocess.check_call(command)

                # Replace the remote channel by its updated copy
                bash_script = f"""set -xe
                chmod -R a+rx {directory}-update/neuro-forge
                rm -Rf {directory}-update/backup/*
                mv {directory}/* {directory}-update/backup
                mv {directory}-update/neuro-forge/* {directory}
                """
                print(f"ssh {destination} /usr/bin/bash << EOF")
                print(bash_script)
                print("EOF")
                p = subprocess.run(
                    [
                        "ssh",
                        destination,
                        "/usr/bin/bash",
                    ],
                    input=bash_script.encode(),
                    check=True,
                )
