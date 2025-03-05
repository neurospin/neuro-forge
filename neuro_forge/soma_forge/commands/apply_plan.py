import git
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import types
import toml
import yaml

import click
from . import cli


def check_build_status(context):
    # Check that bv_maker steps had been done successfully in the right order

    build_info_file = context.pixi_root / "conf" / "build_info.json"
    with open(build_info_file) as f:
        build_info = json.load(f)
    configure_step_info = build_info.get("brainvisa-cmake", {}).get("configure")
    if not configure_step_info:
        raise ValueError(
            f"No bv_maker configuration step information in {build_info_file}"
        )
    status = configure_step_info.get("status")
    if status != "succeeded":
        raise ValueError(f"bv_maker configuration step not successful: {status}")

    build_step_info = build_info.get("brainvisa-cmake", {}).get("build")
    if not build_step_info:
        raise ValueError(f"No bv_maker build step information in {build_info_file}")
    status = build_step_info.get("status")
    if status != "succeeded":
        raise ValueError(f"bv_maker build step not successful: {status}")
    if build_step_info.get("start") <= configure_step_info.get("stop"):
        raise ValueError("bv_maker build step started before the end of configuration.")

    doc_step_info = build_info.get("brainvisa-cmake", {}).get("doc")
    if not doc_step_info:
        raise ValueError(f"No bv_maker doc step information in {build_info_file}")
    status = doc_step_info.get("status")
    if status != "succeeded":
        raise ValueError(f"bv_maker doc step not successful: {status}")
    if doc_step_info.get("start") <= build_step_info.get("stop"):
        raise ValueError("bv_maker doc step started before the end of build.")


def modify_file(context, file, file_contents):
    with open(file, "w") as f:
        f.write(file_contents)


def git_commit(context, repo, modified, message):
    repo = git.Repo(repo)
    repo.git.add(*modified)
    repo.git.commit("-m", message, "-n")
    repo.git.push()


def rebuild(context):
    subprocess.check_call(
        [
            "pixi",
            "run",
            "--manifest-path",
            str(context.pixi_root / "pixi.toml"),
            "bv_maker",
            "configure",
            "build",
            "doc",
        ]
    )


def create_package(context, package, test):
    recipe_dir = context.pixi_root / "plan" / "recipes" / package
    print(f"creating package {package} using test={test} from {recipe_dir}")
    output = context.pixi_root / "plan" / "packages"
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
    for i in channels + [f"file://{output}"]:
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
    with open(context.pixi_root / "plan" / "recipes" / package / "recipe.yaml") as f:
        recipe = yaml.safe_load(f)
    _version = recipe["package"]["version"]


def publish(
    context,
    environment,
    publication_dir,
    packages_dir,
    packages,
    release_history,
    index=False,
    force=False,
):
    publication_dir = pathlib.Path(publication_dir)
    packages_dir = pathlib.Path(packages_dir)
    packages_files = []
    linux_64_files = list((packages_dir / "linux-64").iterdir())
    for package in packages:
        candidates = [
            i
            for i in linux_64_files
            if re.match(rf"{package}-\d+\.\d+\.\d+-.+\.conda", i.name)
        ]
        if len(candidates) > 1:
            raise ValueError(
                f"Several packages files found for {package}: {', '.join(str(i) for i in candidates)}"
            )
        if not candidates:
            raise ValueError(f"No package file found for {package} in {packages_dir}")
        packages_files.append(candidates[0])
    copied = []
    release_history_file_backup = None
    try:
        for src in packages_files:
            r = src.relative_to(packages_dir)
            dest = publication_dir / r
            print(src, "->", dest)
            if not force and dest.exists():
                raise ValueError(f"Destination file {dest} already exist")
            shutil.copy2(src, dest)
            copied.append(dest)
        release_history_file = publication_dir / f"soma-forge-{environment}.json"
        if release_history_file.exists():
            release_history_file_backup = (
                publication_dir / f"soma-forge-{environment}.json.backup"
            )
            os.rename(release_history_file, release_history_file_backup)
        with open(release_history_file, "w") as f:
            copied.append(release_history_file)
            json.dump(release_history, f, indent=4)
        if index:
            subprocess.check_call(["conda", "index", str(publication_dir)])
    except Exception:
        for f in copied:
            os.remove(f)
        if release_history_file_backup is not None:
            os.rename(release_history_file_backup, release_history_file)
        raise
    if release_history_file_backup is not None:
        os.remove(release_history_file_backup)


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
            globals()[action["action"]](
                context, *action.get("args", []), **action.get("kwargs", {})
            )
            action["status"] = "success"
            with open(pixi_root / "plan" / "actions.yaml", "w") as f:
                yaml.safe_dump(actions, f)
