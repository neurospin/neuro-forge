import click
import functools
import operator
import os
from pathlib import Path
import shutil
import subprocess
import yaml

default_channel_dir = "/drf/neuro-forge/public"


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def main():
    pass


@main.command()
@click.option("--recipes_dir", type=click.Path(), default="/drf/neuro-forge/recipes")
@click.argument("channel_dir", type=click.Path())
@click.argument("packages", type=str, nargs=-1)
def build(channel_dir, packages, recipes_dir):
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
    subprocess.check_call(["conda", "index", channel_dir])

    recipes_dir = Path(recipes_dir)

    # Select packages
    neuro_forge = Path(__file__).parent.parent
    if not packages:
        if recipes_dir.exists():
            packages = [
                i.name
                for i in recipes_dir.iterdir()
                if (i / "recipe.yaml").exists()
                and not any(channel_dir.glob(f"*/{i.name}-*.conda"))
            ]
        else:
            packages = []
        packages += [
            i.name
            for i in (neuro_forge / "recipes").iterdir()
            if (i / "recipe.yaml").exists()
            and not any(channel_dir.glob(f"*/{i.name}-*.conda"))
        ]
    # Create selected packages
    for package in packages:
        recipe_file = recipes_dir / package / "recipe.yaml"
        if not recipe_file.exists():
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
        subprocess.check_call(command)

    # Cleanup and create channel index
    subprocess.check_call(["conda", "index", channel_dir])
    to_delete = [channel_dir / i for i in ("bld", "src_cache", ".rattler", ".cache")]
    to_delete.extend(channel_dir.glob("*/.cache"))
    for i in to_delete:
        if i.exists():
            shutil.rmtree(i)


@main.command()
@click.argument("channel_dir", type=click.Path(), default=default_channel_dir)
def publish(channel_dir):
    """Run conda index if necessary and publish channel_dir to
    https://brainvisa.info/neuro-forge"""

    if channel_dir != default_channel_dir:
        # Double check that not using the default directory is done for a
        # good reason
        print(
            f"WARNING: You are about to replace the neuro-forge public "
            "channel with the content of {channel_dir}"
        )
        user_input = input("Confirm ? [Y/N] ")
        if user_input.lower() not in ("y", "yes"):
            print("Operation canceled")
            return
        channel_dir = os.path.abspath(os.path.normpath(channel_dir))

    # Sort all files by modification date and get the most recent
    to_sort = []
    for root, subFolders, files in os.walk(channel_dir):
        for file in files:
            ff = os.path.join(root, file)
            to_sort.append((os.stat(ff).st_mtime, ff))
    recents = [os.path.basename(i[1]) for i in sorted(to_sort)[-2:]]

    # If the most recent is not an index.html file, then run conda index
    if "index.html" not in recents:
        command = ["conda", "index", channel_dir]
    recent = sorted(to_sort)[-1][1]

    # If the most recent is not an index.html file, then run conda index
    if os.path.basename(recent) != "index.html":
        command = ["conda", "index", channel_dir]
        print(" ".join(f"'{i}'" for i in command))
        subprocess.check_call(command)

    # On web server, make a copy of the channel directory using hard links
    command = [
        "ssh",
        "neuroforge@brainvisa.info",
        "cp",
        "-ral",
        "/var/www/html/neuro-forge",
        "/var/www/html/neuro-forge-update",
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
        "neuroforge@brainvisa.info:/var/www/html/neuro-forge-update/neuro-forge/",
    ]
    print(" ".join(f"'{i}'" for i in command))
    subprocess.check_call(command)

    # Replace the remote channel by its updated copy
    bash_script = """set -xe
    chmod -R a+r /var/www/html/neuro-forge-update/neuro-forge
    rm -Rf /var/www/html/neuro-forge-update/backup/*
    mv /var/www/html/neuro-forge/* /var/www/html/neuro-forge-update/backup
    mv /var/www/html/neuro-forge-update/neuro-forge/* /var/www/html/neuro-forge
    """
    print("ssh neuroforge@brainvisa.info /usr/bin/bash << EOF")
    print(bash_script)
    print("EOF")
    p = subprocess.run(
        [
            "ssh",
            "neuroforge@brainvisa.info",
            "/usr/bin/bash",
        ],
        input=bash_script.encode(),
        check=True,
    )
