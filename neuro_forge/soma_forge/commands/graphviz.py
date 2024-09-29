import click
import fnmatch
import re

from . import cli
from ..recipes import sorted_recipies


@cli.command()
@click.argument("packages", type=str, nargs=-1)
@click.option("--conda-forge", type=bool, default=False)
def graphviz(packages, conda_forge):
    """Output a dot file for selected packages (or for all known packages by default)"""
    if not packages:
        packages = ["*"]
    selector = re.compile("|".join(f"(?:{fnmatch.translate(i)})" for i in packages))
    conda_forge_packages = set()
    linked = set()
    print("digraph {")
    print("  node [shape=box, color=black, style=filled]")
    for recipe in sorted_recipies():
        package = recipe["package"]["name"]
        if not selector.match(package):
            continue
        if recipe["soma-forge"]["type"] == "brainvisa-cmake":
            print(f'  "{package}" [fillcolor="aquamarine"]')
        elif recipe["soma-forge"]["type"] == "virtual":
            print(f'  "{package}" [fillcolor="darkolivegreen2"]')
        else:
            print(f'  "{package}" [fillcolor="bisque"]')
        for dependency in recipe["soma-forge"].get("internal-dependencies", []):
            if (package, dependency) not in linked:
                print(f'  "{package}" -> "{dependency}"')
                linked.add((package, dependency))
        if conda_forge:
            for dependency in recipe.get("requirements", {}).get("run", []):
                conda_forge_packages.add(dependency)
                print(f'  "{package}" -> "{dependency}"')
    for package in conda_forge_packages:
        print(f'  "{package}" [fillcolor="aliceblue"]')
    print("}")
