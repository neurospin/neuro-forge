import argparse
import fnmatch
import os
import re
import shutil
import subprocess
import sys

from . import (
    selected_recipes,
    sorted_recipies,
    pixi_root,
    forged_packages,
    read_pixi_config,
    write_pixi_config,
    get_test_commands,
)


def setup(verbose=None):
    # Download neuro-forge sources
    if not (pixi_root / "src" / "neuro-forge").exists():
        (pixi_root / "src").mkdir(exist_ok=True)
        subprocess.check_call(
            [
                "git",
                "-C",
                str(pixi_root / "src"),
                "clone",
                "https://github.com/neurospin/neuro-forge",
            ]
        )

    # Download brainvisa-cmake sources
    if not (pixi_root / "src" / "brainvisa-cmake").exists():
        (pixi_root / "src").mkdir(exist_ok=True)
        subprocess.check_call(
            [
                "git",
                "-C",
                str(pixi_root / "src"),
                "clone",
                "https://github.com/brainvisa/brainvisa-cmake",
            ]
        )


    # Find recipes for external projects and recipes build using bv_maker
    external_recipes = []
    bv_maker_recipes = []
    bv_maker_packages = set()
    for recipe in selected_recipes():
        build = recipe.get("build")
        if build is not None:
            script = build.get("script")
        if build is None or isinstance(script, str) and "BRAINVISA_INSTALL_PREFIX" in script:
            bv_maker_recipes.append(recipe)
            bv_maker_packages.add(recipe["package"]["name"])
        else:
            external_recipes.append(recipe)

    # Build external packages
    for recipe in external_recipes:
        package = recipe["package"]["name"]
        if not any(forged_packages(re.escape(package))):
            result = forge(
                [package], force=False, show=False, check_build=False, verbose=verbose
            )
            if result:
                return result

    # Add internal forge to pixi project
    channel = f"file://{pixi_root / 'forge'}"
    pixi_config = read_pixi_config()
    if channel not in pixi_config["project"]["channels"]:
        pixi_config["project"]["channels"].append(channel)
        write_pixi_config(pixi_config)

    # Compute all packages build and run dependencies
    dependencies = {i["package"]["name"]: set() for i in external_recipes}
    for recipe in external_recipes + bv_maker_recipes:
        for requirement in recipe.get("requirements", {}).get("run", []) + recipe.get(
            "requirements", {}
        ).get("build", []):
            if (
                not isinstance(requirement, str)
                or requirement.startswith("$")
                or requirement.split()[0] == "mesalib"
            ):
                # mesalib is required to compile virtualgl
                # but makes Anatomist crash
                continue
            package, constraint = (requirement.split(None, 1) + [None])[:2]
            if package not in bv_maker_packages:
                dependencies.setdefault(package, set())
                if constraint:
                    existing_constraint = dependencies[package]
                    if constraint not in existing_constraint:
                        existing_constraint.add(constraint)
                        dependencies[package] = existing_constraint

    # Add dependencies to pixi project
    remove = []
    add = []
    for package, constraint in dependencies.items():
        pixi_constraint = pixi_config.get("dependencies", {}).get(package)
        if pixi_constraint is not None:
            if pixi_constraint == "*":
                pixi_constraint = set()
            else:
                pixi_constraint = set(pixi_constraint.split(","))
            if constraint == "*":
                constraint = set()
            if pixi_constraint != constraint:
                remove.append(package)
            else:
                continue
        if constraint:
            add.append(f"{package} {','.join(constraint)}")
        else:
            add.append(f"{package}=*")
    try:
        if remove:
            command = ["pixi", "remove"] + remove
            subprocess.check_call(command)
        if add:
            command = ["pixi", "add"] + add
            subprocess.check_call(command)
    except subprocess.CalledProcessError:
        print(
            "ERROR command failed:",
            " ".join(f"'{i}'" for i in command),
            file=sys.stdout,
            flush=True,
        )
        return 1


def build():
    (pixi_root / "build" / "success").unlink(missing_ok=True)
    # Do not take into account failure on bv_maker sources as long as
    # unstandard branches are used.
    subprocess.call(["bv_maker", "sources"])
    subprocess.check_call(["bv_maker", "configure", "build", "doc"])
    with open(pixi_root / "build" / "success", "w"):
        pass


def forge(packages, force, show, test=True, check_build=True, verbose=None):
    if show and verbose is None:
        verbose = True
    if verbose is True:
        verbose = sys.stdout
    if not packages:
        packages = ["*"]
    selector = re.compile("|".join(f"(?:{fnmatch.translate(i)})" for i in packages))
    if check_build and not (pixi_root / "build" / "success").exists():
        build()
    channels = read_pixi_config()["project"]["channels"]
    for recipe in sorted_recipies():
        package = recipe["package"]["name"]
        recipe_dir = recipe["soma-forge"]["recipe_dir"]
        if selector.match(package):
            if not force:
                # Check for the package exsitence
                if any(forged_packages(f"^{re.escape(package)}$")):
                    if verbose:
                        print(
                            f"Skip existing package {package}",
                            file=verbose,
                            flush=True,
                        )
                    continue
            if verbose:
                print(
                    f"Build {package}",
                    file=verbose,
                    flush=True,
                )
            if not show:
                build_dir = pixi_root / "forge" / "bld" / f"rattler-build_{package}"
                if build_dir.exists():
                    shutil.rmtree(build_dir)
                forge = pixi_root / "forge"
                command = [
                    "rattler-build",
                    "build",
                    "--experimental",
                    "--no-build-id",
                    "-r",
                    recipe_dir,
                    "--output-dir",
                    str(forge),
                ]
                if not test:
                    command.append("--no-test")
                for i in channels + [f"file://{str(forge)}"]:
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
                    return 1


def test_ref():
    test_ref_data_dir = os.environ.get("BRAINVISA_TEST_REF_DATA_DIR")
    if not test_ref_data_dir:
        print("No value for BRAINVISA_TEST_REF_DATA_DIR", file=sys.stderr, flush=True)
        return 1
    os.makedirs(test_ref_data_dir, exists_ok=True)


def test(name):
    test_commands = get_test_commands()
    if name is None:
        print(", ".join(test_commands))
    else:
        test_run_data_dir = os.environ.get("BRAINVISA_TEST_RUN_DATA_DIR")
        if not test_run_data_dir:
            print(
                "No value for BRAINVISA_TEST_RUN_DATA_DIR", file=sys.stderr, flush=True
            )
            return 1
        os.makedirs(test_run_data_dir, exists_ok=True)

        commands = test_commands.get(name)
        if commands is None:
            print("ERROR: No test named", name, file=sys.stderr, flush=True)
            return 1
        for command in commands:
            try:
                subprocess.check_call(command, shell=True)
            except subprocess.CalledProcessError:
                print(
                    "ERROR command failed:",
                    command,
                    file=sys.stderr,
                    flush=True,
                )
                return 1


def dot(packages, conda):
    conda_forge = set()
    print("digraph {")
    print("  node [shape=box, color=black, style=filled]")
    for recipe in selected_recipes(packages):
        package = recipe["package"]["name"]
        if recipe["soma-forge"]["type"] == "brainvisa-cmake":
            print(f'  "{package}" [fillcolor="aquamarine"]')
        elif recipe["soma-forge"]["type"] == "virtual":
            print(f'  "{package}" [fillcolor="darkolivegreen2"]')
        else:
            print(f'  "{package}" [fillcolor="bisque"]')
        for dependency in (
            recipe["soma-forge"].get("requirements", {}).get("brainvisa-cmake", [])
        ):
            print(f'  "{package}" -> "{dependency}"')
        for dependency in (
            recipe["soma-forge"].get("requirements", {}).get("soma-forge", [])
        ):
            print(f'  "{package}" -> "{dependency}"')
        if conda:
            for dependency in (
                recipe["soma-forge"].get("requirements", {}).get("conda-forge", [])
            ):
                conda_forge.add(dependency)
                print(f'  "{package}" -> "{dependency}"')
    for package in conda_forge:
        print(f'  "{package}" [fillcolor="aliceblue"]')
    print("}")


parser = argparse.ArgumentParser(
    prog="python -m soma_forge",
)

subparsers = parser.add_subparsers(
    required=True,
    title="subcommands",
)

parser_setup = subparsers.add_parser("setup", help="setup environment")
parser_setup.set_defaults(func=setup)
parser_build = subparsers.add_parser(
    "build", help="get sources, compile and build brainvisa-cmake components"
)
parser_build.set_defaults(func=build)

parser_forge = subparsers.add_parser("forge", help="create conda packages")
parser_forge.set_defaults(func=forge)
parser_forge.add_argument(
    "-f",
    "--force",
    action="store_true",
    help="build selected packages even it they exists",
)
parser_forge.add_argument(
    "--no-test",
    dest="test",
    action="store_false",
    help="do not run tests while building packages",
)
parser_forge.add_argument(
    "-s",
    "--show",
    action="store_true",
    help="do not build packages, only show the ones that are selected",
)
parser_forge.add_argument(
    "packages",
    type=str,
    nargs="*",
    help="select packages using their names or Unix shell-like patterns",
)
parser_test = subparsers.add_parser("test", help="manage brainvisa-cmake tests")
parser_test.add_argument(
    "name",
    type=str,
    nargs="?",
    default=None,
    help="name of the test to run. No value just list the possible names.",
)
parser_test.set_defaults(func=test)

parser_dot = subparsers.add_parser(
    "dot", help="create a graphviz dot file showing packages dependencies"
)
parser_dot.add_argument(
    "-c",
    "--conda",
    action="store_true",
    help="include conda-forge packages",
)
parser_dot.add_argument(
    "packages",
    type=str,
    nargs="*",
    help="select packages using their names or Unix shell-like patterns",
)
parser_dot.set_defaults(func=dot)

args = parser.parse_args(sys.argv[1:])
kwargs = vars(args).copy()
del kwargs["func"]
sys.exit(args.func(**kwargs))
