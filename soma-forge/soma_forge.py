import click
import fnmatch
import git
import itertools
import json
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import toml
import yaml

from rich.console import Console
from rich.table import Table
from rich.pretty import Pretty
import rich.traceback
rich.traceback.install()

default_qt = 5
default_capsul = 2
default_python = 3.11

# Git branches to select for brainvisa-cmake components given
# Capsul version (when different from defautl branch)
components_branch = {
    "3": {
        "soma-base": "6.0",
        "capsul": "3.0",
        "anatomist-gpl": "capsul3",
        "morphologist": "capsul3",
        "morphologist-gpl": "capsul3",
        "morpho-deepsulci": "capsul3",
    }
}

bv_maker_cfg_template = """[ source $CASA_SRC ]
  default_source_dir = {{component}}
  ignore_git_failure=ON

{components_source}

[ build $CASA_BUILD ]
  default_steps = configure build doc
  make_options = -j$NCPU
  cmake_options += -DPIXI=$CASA
  build_type = Release
  packaging_thirdparty = OFF
  clean_config = ON
  clean_build = ON
  test_ref_data_dir = $CASA_TESTS/ref
  test_run_data_dir = $CASA_TESTS/test

{components_build}
"""


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def cli():
    global console

    console = Console()


@cli.command()
@click.option(
    "-p",
    "--python",
    type=click.Choice(["3.10", "3.11", "3.12"]),
    default=None,
    help=f"Python version (default=config file value or {default_python})",
)
@click.option(
    "-c",
    "--capsul",
    type=click.Choice(["2", "3"]),
    default=None,
    help=f"Capsul major version (default=config file value or {default_capsul})",
)
@click.option(
    "-q",
    "--qt",
    type=click.Choice(["5", "6"]),
    default=None,
    help=f"Qt major version (default=config file value or {default_qt})",
)
@click.option("--force", is_flag=True)
@click.argument("directory", type=click.Path())
@click.argument("packages", type=str, nargs=-1)
def init(directory, packages, python, capsul, qt, force):
    """Create or reconfigure a full BrainVISA development directory"""
    if not packages:
        packages = ["all"]

    neuro_forge_url = "https://brainvisa.info/neuro-forge"
    pixi_root = pathlib.Path(directory)
    if not pixi_root.exists():
        pixi_root.mkdir()
        subprocess.check_call(
            [
                "pixi",
                "init",
                "-c",
                neuro_forge_url,
                "-c",
                "nvidia",
                "-c",
                "pytorch",
                "-c",
                "conda-forge",
                str(pixi_root),
            ]
        )

    build_dir = pixi_root / "build"
    conf_dir = pixi_root / "conf"
    conf_dir.mkdir(exist_ok=True)

    build_options_file = conf_dir / "build_options.json"
    build_options = {
        "packages": packages,
    }
    if build_options_file.exists():
        with open(build_options_file) as f:
            current_build_options = json.load(f)
        build_options = current_build_options.copy()
    for name, default in (
        ("python", default_python),
        ("capsul", default_capsul),
        ("qt", default_qt),
    ):
        build_options[name] = locals()[name] or default

    if force or not build_options_file.exists():
        with open(build_options_file, "w") as f:
            json.dump(build_options, f, indent=4)
    else:
        with open(build_options_file) as f:
            current_build_options = json.load(f)
        if current_build_options != build_options and build_dir.exists():
            console.print(
                f"[red]Existing build options in [bold]{build_options_file}[/bold] differs from the selected ones[/red]"
            )
            table = Table()
            table.add_column("existing options")
            table.add_column("selected options")
            table.add_row(Pretty(current_build_options), Pretty(build_options))
            console.print(table)
            console.print(
                "Either remove the directory [code]{build_dir}[/code] or use [code]--force[/code] option."
            )
            sys.exit(1)
        with open(build_options_file, "w") as f:
            json.dump(build_options, f, indent=4)

    pixi_config = read_pixi_config(pixi_root)
    pixi_project_name = (
        f"{'-'.join(packages)}-py{build_options['python']}"
        f"-cap{build_options['capsul']}"
        f"-qt{build_options['qt']}"
    )
    modified = False
    if pixi_config["project"]["name"] != pixi_project_name:
        pixi_config["project"]["name"] = pixi_project_name
        modified = True
    if "libjpeg-turbo" not in pixi_config["dependencies"]:
        pixi_config["dependencies"]["libjpeg-turbo"] = {
            "channel": "conda-forge",
            "version": ">=3.0.0",
        }
        modified = True

    # Compute all packages build and run dependencies
    dependencies = {}
    components = {}
    for recipe in selected_recipes(packages or ["all"]):
        package = recipe["package"]["name"]
        print(package, recipe["soma-forge"]["type"])
        for component in recipe.get("components", []):
            branch = components_branch.get(build_options["capsul"], {}).get(
                component, "master"
            )
            components.setdefault(package, {})[component] = branch
            print("   ", component, branch)
        for requirement in recipe.get("requirements", {}).get("run", []) + recipe.get(
            "requirements", {}
        ).get("build", []):
            if (
                not isinstance(requirement, str)
                or requirement.startswith("$")
                or requirement.split()[0] == "mesalib"
            ):
                # mesalib makes Anatomist crash
                continue
            package, constraint = (requirement.split(None, 1) + [None])[:2]
            dependencies.setdefault(package, set())
            if constraint:
                existing_constraint = dependencies[package]
                if constraint not in existing_constraint:
                    existing_constraint.add(constraint)
                    dependencies[package] = existing_constraint

    # Generate bv_maker.cfg
    components_source = []
    components_build = []
    for package, cb in components.items():
        components_source.append(f"# Components of package {package}")
        components_build.append(f"# Components of package {package}")
        for component, branch in cb.items():
            components_source.append(f"brainvisa {component} {branch}")
            components_build.append(f"brainvisa {component} {branch} $CASA_SRC")
    bv_maker_cfg = pixi_root / "conf" / "bv_maker.cfg"
    if bv_maker_cfg.exists() and not force:
        console.print(
            f"[red]File [code]{bv_maker_cfg}[/code] exist, remove it or use [code]--force[/code] option."
        )
    with open(bv_maker_cfg, "w") as f:
        f.write(
            bv_maker_cfg_template.format(
                components_source="    " + "\n    ".join(components_source),
                components_build="    " + "\n    ".join(components_build),
            )
        )
    soma_forge_dependencies = {
        "cmake": "*",
        "gcc": "*",
        "git": "*",
        "gxx": "*",
        "pytest": "*",
        "pip": "*",
        "pyaml": "*",
        "python": "*",
        "rattler-build": [">=0.13"],
        "six": "*",
        "sphinx": "*",
        "toml": "*",
        "libglu": "*",
        "mesalib-devel-only": "*",
        "mesa-libgl-devel-cos7-x86_64": "*",
        "virtualgl": "*",
        "libglvnd-devel-cos7-x86_64": "*",
    }

    # Add dependencies to pixi.toml
    for package, constraint in itertools.chain(
        soma_forge_dependencies.items(), dependencies.items()
    ):
        pixi_constraint = pixi_config.get("dependencies", {}).get(package)
        if pixi_constraint is not None:
            if pixi_constraint == "*":
                pixi_constraint = set()
            else:
                pixi_constraint = set(pixi_constraint.split(","))
            if constraint == "*":
                constraint = set()
            if pixi_constraint != constraint:
                del pixi_config["dependencies"][package]
                modified = True
                # remove.append(package)
            else:
                continue
        if constraint:
            pixi_config.setdefault("dependencies", {})[package] = ",".join(constraint)
        else:
            pixi_config.setdefault("dependencies", {})[package] = "*"

    shutil.copy(
        pathlib.Path(__file__).parent / "activate.sh",
        pixi_root / "activate.sh",
    )
    activation_script = "activate.sh"
    scripts = pixi_config.get("activation", {}).get("scripts")
    if scripts is None:
        pixi_config["activation"] = {"scripts": [activation_script]}
        modified = True
    elif activation_script not in scripts:
        scripts.append(activation_script)
        modified = True
    if modified:
        write_pixi_config(pixi_root, pixi_config)

    # Download brainvisa-cmake sources
    if not (pixi_root / "src" / "brainvisa-cmake").exists():
        (pixi_root / "src").mkdir(exist_ok=True)
        git.Repo.clone_from(
            "https://github.com/brainvisa/brainvisa-cmake",
            str(pixi_root / "src" / "brainvisa-cmake"),
        )


def read_recipes():
    """
    Iterate over all recipes files defined in soma-forge.
    """
    for recipe_file in (pathlib.Path(__file__).parent / "recipes").glob(
        "*.yaml"
    ):
        with open(recipe_file) as f:
            recipe = yaml.safe_load(f)
            yield recipe


def selected_recipes(selection=None):
    """
    Iterate over recipes selected in configuration and their dependencies.
    """
    # Read recipes
    recipes = {r["package"]["name"]: r for r in read_recipes()}

    # Parse direct dependencies
    for package, recipe in recipes.items():
        if recipe.get("components"):
            build_requirements = recipe.get("requirements", {}).get("build", [])
            if any(
                i for i in build_requirements if i.startswith("${{") and "compiler" in i
            ):
                recipe["soma-forge"] = {"type": "compiled"}
            else:
                recipe["soma-forge"] = {"type": "interpreted"}
        else:
            recipe["soma-forge"] = {"type": "virtual"}

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
        dependencies = recipe.get("internal-dependencies", [])
        stack.extend(i for i in dependencies if i not in done)


def sorted_recipies():
    """
    Iterate over recipes sorted according to their depencencies starting with a
    package without dependency.
    """
    recipes = {r["package"]["name"]: r for r in selected_recipes()}
    ready = set()
    inverted_dependencies = {}
    for package, recipe in recipes.items():
        dependencies = (
            recipe["soma-forge"]
            .get("requirements", {})
            .get("brainvisa-cmake", set())
            .union(
                recipe["soma-forge"].get("requirements", {}).get("soma-forge", set())
            )
        )
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
            dependencies = (
                recipes[dependent]["soma-forge"]
                .get("requirements", {})
                .get("brainvisa-cmake", set())
                .union(
                    recipes[dependent]["soma-forge"]
                    .get("requirements", {})
                    .get("soma-forge", set())
                )
            )
            if all(d in done for d in dependencies):
                ready.add(dependent)


def forged_packages(name_re):
    """
    Iterate over name of packages that exists in local forge
    """
    if isinstance(name_re, str):
        name_re = re.compile(name_re)
    for repodata_file in (pixi_root / "forge").glob("*/repodata.json"):
        with open(repodata_file) as f:
            repodata = json.load(f)
        for file, package_info in repodata.get("packages.conda", {}).items():
            name = package_info["name"]
            if name_re.match(name):
                package_info["path"] = str(pathlib.Path(repodata_file).parent / file)
                yield package_info


def read_pixi_config(pixi_root):
    """
    Read pixi.toml file
    """
    with open(pixi_root / "pixi.toml") as f:
        return toml.load(f)


def write_pixi_config(pixi_root, pixi_config):
    """
    wite pixi.toml file
    """
    with open(pixi_root / "pixi.toml", "w") as f:
        toml.dump(pixi_config, f, encoder=toml.TomlPreserveCommentEncoder())


def get_test_commands(log_lines=None):
    """
    Use ctest to extract command lines to execute in order to run tests.
    This function returns a dictionary whose keys are name of a test (i.e.
    'axon', 'soma', etc.) and values are a list of commands to run to perform
    the test.
    """
    cmd = ["ctest", "--print-labels"]
    # universal_newlines is the old name to request text-mode (text=True)
    o = subprocess.check_output(cmd, bufsize=-1, universal_newlines=True)
    labels = [i.strip() for i in o.split("\n")[2:] if i.strip()]
    if log_lines is not None:
        log_lines += ["$ " + " ".join(shlex.quote(arg) for arg in cmd), o, "\n"]
    tests = {}
    for label in labels:
        cmd = ["ctest", "-V", "-L", f"^{label}$"]
        env = os.environ.copy()
        env["BRAINVISA_TEST_REMOTE_COMMAND"] = "echo"
        p = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=-1,
            universal_newlines=True,
            env=env,
        )
        o, stderr = p.communicate()
        if log_lines is not None:
            log_lines += ["$ " + " ".join(shlex.quote(arg) for arg in cmd), o, "\n"]
        if p.returncode != 0:
            # We want to hide stderr unless ctest returns a nonzero exit
            # code. In the case of test filtering where no tests are
            # matched (e.g. with ctest_options=['-R', 'dummyfilter']), the
            # annoying message 'No tests were found!!!' is printed to
            # stderr by ctest, but it exits with return code 0.
            sys.stderr.write(stderr)
            raise RuntimeError("ctest failed with the above error")
        o = o.split("\n")
        # Extract the third line that follows each line containing ': Test
        # command:'
        commands = []
        i = 0
        while i < len(o):
            line = o[i]
            m = re.match(r"(^[^:]*): Test command: .*$", line)
            if m:
                prefix = f"{m.group(1)}: "
                command = None
                i += 1
                while i < len(o) and o[i].startswith(prefix):
                    command = o[i][len(prefix) :]
                    i += 1
                if command:
                    commands.append(command)
            i += 1
        if commands:
            tests[label] = commands
    if log_lines is not None:
        log_lines += [
            "Final test dictionary:",
            json.dumps(tests, indent=4, separators=(",", ": ")),
        ]
    return tests


def build():
    (pixi_root / "build" / "success").unlink(missing_ok=True)
    # Do not take into account failure on bv_maker sources as long as
    # unstandard branches are used.
    bv_maker = str(pixi_root / "src" / "brainvisa-cmake" / "bin" / "bv_maker")
    subprocess.call([bv_maker, "sources"])
    subprocess.check_call([bv_maker, "configure", "build", "doc"])
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


def main():
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

if __name__ == '__main__':
    cli()
