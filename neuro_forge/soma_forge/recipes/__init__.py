import pathlib
import yaml


def read_recipe(package):
    """
    Read a single recip given its package name
    """
    recipe_file = pathlib.Path(__file__).parent / f"{package}.yaml"
    with open(recipe_file) as f:
        recipe = yaml.safe_load(f)
    return recipe


def read_recipes():
    """
    Iterate over all recipes files defined in soma-forge.
    """
    for recipe_file in (pathlib.Path(__file__).parent).glob("*.yaml"):
        with open(recipe_file) as f:
            recipe = yaml.safe_load(f)
            yield recipe


def selected_recipes(selection=None):
    """
    Iterate over recipes selected in configuration and their dependencies.
    """
    # Read recipes
    recipes = {r["package"]["name"]: r for r in read_recipes()}

    all_packages = set(recipes)

    metapackages = {
        "all": all_packages,
    }
    if not selection:
        selection = ["all"]
    selected_packages = set()
    for s in selection:
        if s.startswith("-"):
            s = s[1:].strip()
            remove = True
        else:
            remove = False
        m = metapackages.get(s)
        if m is not None:
            s = m
        else:
            s = {s}
        if remove:
            selected_packages = selected_packages.difference(s)
        else:
            selected_packages.update(s)

    # Walk over selected packages and dependencies
    stack = list(selected_packages)
    done = set()
    while stack:
        package = stack.pop(0)
        if package in done:
            continue
        recipe = recipes[package]
        yield recipe
        done.add(package)
        dependencies = recipe["soma-forge"].get("internal-dependencies", [])
        stack.extend(i for i in dependencies if i not in done)


def sorted_recipies():
    """
    Iterate over recipes sorted according to their dependencies starting with a
    package without dependency.
    """
    recipes = {r["package"]["name"]: r for r in selected_recipes()}
    ready = set()
    inverted_dependencies = {}
    for package, recipe in recipes.items():
        dependencies = recipe["soma-forge"].get("internal-dependencies", [])
        if not dependencies:
            ready.add(package)
        for dependency in dependencies:
            inverted_dependencies.setdefault(dependency, set()).add(package)

    done = set()
    while ready:
        package = ready.pop()
        yield recipes[package]
        done.add(package)
        for dependent in inverted_dependencies.get(package, []):
            dependencies = recipe.get("internal-dependencies", [])
            if all(d in done for d in dependencies):
                ready.add(dependent)
