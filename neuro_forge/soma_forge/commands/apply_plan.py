import pathlib
import shutil
import subprocess
import sys
import types
import toml
import yaml

import click
from . import cli


def create_package(context, package, test):
    recipe_dir = context.pixi_root / "plan" / "recipes" / package
    print(f"creating package {package} using test={test} from {recipe_dir}")
    output = context.pixi_root / "packages"
    build_dir = output / "bld" / f"rattler-build_{package}"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    command = [
        "rattler-build",
        "build",
        "--experimental",
        "--no-build-id",
        "-r",
        recipe_dir,
        "--output-dir",
        str(output),
    ]
    if not test:
        command.append("--no-test")
    with open(context.pixi_root / "pixi.toml") as f:
        pixi_toml = toml.load(f)
    channels = pixi_toml["project"]["channels"]
    for i in channels + [f"file://{str(output)}"]:
        command.extend(["-c", i])
    try:
        subprocess.check_call(command)
    except subprocess.CalledProcessError:
        print(
            "ERROR command failed:",
            " ".join(f"'{i}'" for i in command),
            file=sys.stderr,
            flush=True,
        )
        raise


@cli.command()
@click.argument("directory", type=click.Path())
def apply_plan(directory):
    pixi_root = pathlib.Path(directory).absolute()
    with open(pixi_root / "plan" / "actions.yaml") as f:
        actions = yaml.safe_load(f)
    context = types.SimpleNamespace()
    context.pixi_root = pixi_root
    for action in actions:
        if action.get("status") != "success":
            globals()[action["action"]](context, *action["args"], **action["kwargs"])
            action["status"] = "success"
            with open(pixi_root / "plan" / "actions.yaml", "w") as f:
                yaml.safe_dump(actions, f)