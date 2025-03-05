import pathlib

import click
import git

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
            branches = {i.name.rsplit("/", 1)[-1] for i in repo.remote().refs}
            if branch is None:
                branch = "master" if "master" in branches else "main"

            repo.git.fetch()
            non_merged = {
                i.split(None, 1)[0]
                for i in repo.git.branch("-r", "--no-merge").split("\n")
                if i
            }
            if f"origin/{branch}" in non_merged:
                print(f"git -C '{src}' merge --no-edit origin/{branch}")
                print(f"git -C '{src}' push")
        else:
            stack.extend(i for i in src.iterdir() if i.is_dir())
