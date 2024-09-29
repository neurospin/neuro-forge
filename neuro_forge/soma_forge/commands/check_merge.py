import git
import pathlib

import click
from . import cli


@cli.command()
@click.argument("src", type=click.Path())
@click.option("--branch", type=str, default=None)
def check_merge(src, branch):
    stack = [pathlib.Path(src)]
    while stack:
        src = stack.pop()
        if (src / ".git").exists():
            repo = git.Repo(str(src))
            branches = set(i.name.rsplit("/", 1)[-1] for i in repo.remote().refs)
            if branch is None:
                if "master" in branches:
                    branch = "master"
                else:
                    branch = "main"

            repo.git.fetch()
            non_merged = set(
                i.split(None, 1)[0]
                for i in repo.git.branch("-r", "--no-merge").split("\n")
                if i
            )
            if f"origin/{branch}" in non_merged:
                print(f"git -C '{src}' merge origin/{branch}")
                print(f"git -C '{src}' push")
        else:
            stack.extend(i for i in src.iterdir() if i.is_dir())