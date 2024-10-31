import click
import fnmatch
import re

from . import cli
from ..recipes import sorted_recipies
from ... import find_neuro_forge_packages


@cli.command()
@click.argument("packages", type=str, nargs=-1)
@click.option("--conda-forge", type=bool, default=False)
def graphviz(packages, conda_forge):
    """Output a dot file for selected packages (or for all known packages by default)"""
    if not packages:
        packages = ["*"]
    selector = re.compile("|".join(f"(?:{fnmatch.translate(i)})" for i in packages))
    neuro_forge_packages = set()
    conda_forge_packages = set()
    linked = set()
    print("digraph {")
    print("  node [shape=box, color=black, style=filled]")
    recipes ={recipe["package"]["name"]: recipe for recipe in sorted_recipies()}
    selected_recipes = set()
    stack = [i for i in recipes if selector.match(i)]
    while stack:
        package = stack.pop(0)
        selected_recipes.add(package)
        recipe = recipes[package]
        for dependency in recipe["soma-forge"].get("internal-dependencies", []):
            if dependency not in selected_recipes:
                stack.append(dependency)

    all_neuro_forge_packages = set(find_neuro_forge_packages())
    for package in selected_recipes:
        recipe = recipes[package]
        if recipe["soma-forge"]["type"] == "interpreted":
            print(f'  "{package}" [fillcolor="aquamarine2"]')
        elif recipe["soma-forge"]["type"] == "compiled":
            print(f'  "{package}" [fillcolor="darkgreen",fontcolor=white]')
        elif recipe["soma-forge"]["type"] == "virtual":
            print(f'  "{package}" [fillcolor="powderblue"]')
        else:
            print(f'  "{package}" [fillcolor="bisque"]')
        for dependency in recipe["soma-forge"].get("internal-dependencies", []):
            if (package, dependency) not in linked:
                print(f'  "{package}" -> "{dependency}"')
                linked.add((package, dependency))
        for dependency in recipe.get("requirements", {}).get("run", []):
            if dependency in all_neuro_forge_packages:
                neuro_forge_packages.add(dependency)
                print(f'  "{package}" -> "{dependency}"')
            elif conda_forge:
                conda_forge_packages.add(dependency)
                print(f'  "{package}" -> "{dependency}"')
    for package in neuro_forge_packages:
        print(f'  "{package}" [fillcolor="bisque"]')
    for package in conda_forge_packages:
        print(f'  "{package}" [fillcolor="aliceblue"]')
    print("}")
