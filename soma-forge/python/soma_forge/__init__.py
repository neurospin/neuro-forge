import argparse
import fnmatch
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

pixi_root = pathlib.Path(os.environ["PIXI_PROJECT_ROOT"])


def read_recipes():
    """
    Iterate over all recipes files defined in soma-forge.
    """
    for recipe_file in (
        pixi_root / "src" / "neuro-forge" / "soma-forge" / "recipes"
    ).glob("*/recipe.yaml"):
        with open(recipe_file) as f:
            recipe = yaml.safe_load(f)
            recipe["soma-forge"] = {"recipe_dir": str(recipe_file.parent)}
            yield recipe


def selected_recipes(selection=None):
    """
    Iterate over recipes selected in configuration and their dependencies.
    """
    # Read recipes
    recipes = {r["package"]["name"]: r for r in read_recipes()}

    # Parse direct dependencies
    no_dependency = set(recipes)
    for package, recipe in recipes.items():
        build = recipe.get("build")
        if build:
            script = build.get("script")
            if isinstance(script, str) and "BRAINVISA_INSTALL_PREFIX" in script:
                recipe["soma-forge"]["type"] = "brainvisa-cmake"
            else:
                recipe["soma-forge"]["type"] = "soma-forge"
        else:
            recipe["soma-forge"]["type"] = "virtual"

        for requirement in recipe.get("requirements").get("run", []):
            if not isinstance(requirement, str) or requirement.startswith("$"):
                continue
            dependency = requirement.split(None, 1)[0]
            no_dependency.discard(dependency)
            if dependency not in recipes:
                recipe["soma-forge"].setdefault("requirements", {}).setdefault(
                    "conda-forge", set()
                ).add(dependency)
            else:
                type = recipe["soma-forge"]["type"]
                if type == "virtual":
                    type = "brainvisa-cmake"
                recipe["soma-forge"].setdefault("requirements", {}).setdefault(
                    type, set()
                ).add(dependency)

    # Read soma-forge configuration
    config_file = pixi_root / "conf" / "soma-forge.yaml"
    all_packages = set(recipes)
    selected_packages = all_packages
    if config_file.exists():
        with open(config_file) as f:
            config = yaml.safe_load(f)
            s = config.get("packages")
            if s:
                selected_packages = list(s)
    metapackages = {
        "all": all_packages,
        "selected": selected_packages,
    }
    if not selection:
        selection = ["selected"]
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
        dependencies = (
            recipe["soma-forge"]
            .get("requirements", {})
            .get("brainvisa-cmake", set())
            .union(
                recipe["soma-forge"].get("requirements", {}).get("soma-forge", set())
            )
        )
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


def read_pixi_config():
    """
    Read pixi.toml file
    """
    with open(pixi_root / "pixi.toml") as f:
        return toml.load(f)


def write_pixi_config(pixi_config):
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

def setup(verbose=None):
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
        if (
            build is None
            or isinstance(script, str)
            and "BRAINVISA_INSTALL_PREFIX" in script
        ):
            bv_maker_recipes.append(recipe)
            bv_maker_packages.add(recipe["package"]["name"])
        else:
            external_recipes.append(recipe)


    # Add pytorch channels and activation to pixi project
    soma_forge_dependencies = {
        "cmake": "*",
        "gcc": "*",
        "git": "*",
        "gxx": "*",
        "pytest": "*",
        "pip": "*",
        "pyaml": "*",
        "python": "*",
        "rattler-build": ">=0.13",
        "six": "*",
        "sphinx": "*",
        "toml": "*",
        "libglu": "*",
        "mesalib-devel-only": "*",
        "mesa-libgl-devel-cos7-x86_64": "*",
        "virtualgl": "*",
        "libglvnd-devel-cos7-x86_64": "*",
    }
    pixi_config = read_pixi_config()
    modified = False
    channels = pixi_config["project"]["channels"]
    if "pytorch" not in channels:
        channels.remove("conda-forge")
        channels.extend(["nvidia", "pytorch", "conda-forge"])
        modified = True
    if "libjpeg-turbo" not in pixi_config["dependencies"]:
        pixi_config["dependencies"]["libjpeg-turbo"] = {
            "channel": "conda-forge",
            "version": ">=3.0.0",
        }
        modified = True
    for package, version in soma_forge_dependencies.items():
        if package not in pixi_config["dependencies"]:
            pixi_config["dependencies"][package] = version
            modified = True
    activation_script = "soma-forge/activate.sh"
    scripts = pixi_config.get("activation", {}).get("scripts")
    if scripts is None:
        pixi_config["activation"] = {"scripts": [activation_script]}
        modified = True
    elif activation_script not in scripts:
        scripts.append(activation_script)
        modified = True
    if modified:
        write_pixi_config(pixi_config)

    # Copy default conf directory
    if not (pixi_root / "conf").exists():
        shutil.copytree(pathlib.Path(__file__).parent / "conf", pixi_root / "conf")

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
                # mesalib makes Anatomist crash
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
