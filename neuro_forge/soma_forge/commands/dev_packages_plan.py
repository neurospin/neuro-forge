import fnmatch
import git
import itertools
import json
import os
import pathlib
import re
import shlex
import subprocess
import sys
import toml
import yaml

import click
from . import cli
from ..recipes import sorted_recipies


def forged_packages(pixi_root, name_re):
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


def brainvisa_cmake_component_version(src):
    # Check pyproject.toml
    pyproject_toml = src / "pyproject.toml"
    if pyproject_toml.exists():
        with open(pyproject_toml) as f:
            p = toml.load(f)
        version = p.get("project", {}).get("version")
        if version is None:
            raise ValueError(f"Cannot find version in {pyproject_toml}")

    # Check info.py
    info_py = list(
        itertools.chain(
            src.glob("info.py"), src.glob("*/info.py"), src.glob("python/*/info.py")
        )
    )
    if info_py:
        if len(info_py) > 1:
            raise ValueError(
                f"Cannot choose info.py among: {', '.join(str(i) for i in info_py)}"
            )

        info_py = info_py[0]
        d = {}
        with open(info_py) as f:
            exec(compile(f.read(), info_py, "exec"), d, d)
        return f"{d['version_major']}.{d['version_minor']}.{d['version_micro']}"

    # Check project_info.cmake
    project_info = src / "project_info.cmake"
    if not project_info.exists():
        project_info = src / "cmake" / "project_info.cmake"
    if project_info.exists():
        v = [None, None, None]
        with open(project_info) as f:
            p = re.compile(r"\s*set\(\s*([^ \t]*)\s*(.*[^ \t])\s*\)")
            for line in f:
                match = p.match(line)
                if match:
                    variable, value = match.groups()
                    if variable == "BRAINVISA_PACKAGE_VERSION_MAJOR":
                        v[0] = value
                    elif variable == "BRAINVISA_PACKAGE_VERSION_MINOR":
                        v[1] = value
                    elif variable == "BRAINVISA_PACKAGE_VERSION_PATCH":
                        v[2] = value
        return ".".join(v)

    raise ValueError(
        f"Cannot find brainvisa-cmake component version in {pyproject_toml}"
    )


@cli.command()
@click.argument("directory", type=click.Path())
def debug(directory):
    pixi_root = pathlib.Path(directory)
    for src in (pixi_root / "src").iterdir():
        if src.is_dir():
            print(src.name, "==", brainvisa_cmake_component_version(src))


@cli.command()
@click.option("--force", is_flag=True)
@click.option("--test", type=bool, default=False)
@click.argument("directory", type=click.Path())
@click.argument("packages", type=str, nargs=-1)
def dev_packages_plan(directory, packages, force, test=True):
    pixi_root = pathlib.Path(directory).absolute()
    if not packages:
        packages = ["*"]
    selector = re.compile("|".join(f"(?:{fnmatch.translate(i)})" for i in packages))

    build_info_file = pixi_root / "conf" / "build_info.json"
    with open(build_info_file) as f:
        build_info = json.load(f)

    if not force:
        # Check that bv_maker steps had been done successfully in the right order

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
            raise ValueError(
                "bv_maker build step started before the end of configuration."
            )

        doc_step_info = build_info.get("brainvisa-cmake", {}).get("doc")
        if not doc_step_info:
            raise ValueError(f"No bv_maker doc step information in {build_info_file}")
        status = doc_step_info.get("status")
        if status != "succeeded":
            raise ValueError(f"bv_maker doc step not successful: {status}")
        if doc_step_info.get("start") <= build_step_info.get("stop"):
            raise ValueError("bv_maker doc step started before the end of build.")

    # Increase build number
    build_number = build_info["build_number"] = build_info.get("build_number", 0) + 1
    with open(build_info_file, "w") as f:
        json.dump(build_info, f, indent=4)

    plan = pixi_root / "plan"
    recipes = {}
    all_packages = build_info["all_packages"]
    selected_packages = set()
    # Get ordered selection of recipes according to
    # user selection and modification since last
    # packaging
    history_file = plan / "history.json"
    if history_file.exists():
        with open(history_file) as f:
            history = json.load(f)
    else:
        history = {}
    for recipe in sorted_recipies():
        package = recipe["package"]["name"]
        if package not in all_packages:
            print(f"Skip package {package} (not in soma-build tree)")
            continue
        if not selector.match(package):
            print(f"Ignore package {package} (excluded by parameters)")
            continue
        components = recipe["soma-forge"].get("components", [])
        if components:
            # Parse components and do the following:
            #  - get version of first component in package_version
            #  - put error messages in src_errors if source trees are not clean
            #  - Get current git changeset of each component source tree in
            #    changesets
            package_version = None
            src_errors = []
            changesets = {}
            for component in components:
                src = pixi_root / "src" / component
                if package_version is None:
                    package_version = brainvisa_cmake_component_version(src)
                repo = git.Repo(src)
                if repo.is_dirty():
                    src_errors.append(f"repository {src} contains uncomited files")
                elif repo.untracked_files:
                    src_errors.append(f"repository {src} has local modifications")
                changesets[component] = str(repo.head.commit)
            if changesets != history.get(package, {}).get("changesets"):
                from pprint import pprint
                print(
                    f"Select {package} for building beacause detected changes in source"
                )
                selected_packages.add(package)
            else:
                print(f"No change detected in package {package}")

            # Set build section in recipe
            recipe.setdefault("build", {})["number"] = build_number
            recipe["build"][
                "string"
            ] = f"{build_info['build_string']}_{build_info['build_number']}"
            recipe["build"]["script"] = "\n".join(
                (
                    f"cd '{pixi_root}'",
                    f"pixi run --manifest-path='{pixi_root}/pixi.toml' bash << END",
                    'cd "\\$CASA_BUILD"',
                    'export BRAINVISA_INSTALL_PREFIX="$PREFIX"',
                    f"for component in {' '.join(components)}; do",
                    "  make install-\\${component}",
                    "  make install-\\${component}-dev",
                    "  make install-\\${component}-usrdoc",
                    "  make install-\\${component}-devdoc",
                    "done",
                    "END",
                )
            )

            # Set package version in recipe
            recipe["package"]["version"] = package_version
            # Save information in recipe because we do not know yet
            # if package is selected for building (known later via
            # dependencies).
            recipe["soma-forge"]["src_errors"] = src_errors
            recipe["soma-forge"]["changesets"] = changesets
        elif recipe["soma-forge"]["type"] == "virtual":
            version = history.get("package", {}).get("version")
            if version is None:
                version = f"{build_info['environment']}.0"
            else:
                version = version.split(".")
                version[2] = str(int(version[2]) + 1)
                version = ".".join(version)
            recipe["package"]["version"] = version
            # Set build section in recipe
            recipe.setdefault("build", {})["number"] = build_number
            recipe["build"][
                "string"
            ] = f"{build_info['build_string']}_{build_info['build_number']}"
            print(
                f"Select virtual package {package} {version} for building"
            )
            selected_packages.add(package)
        else:
            raise Exception(
                f"Invalid recipe for {package} (bad type or no component defined)"
            )
        recipes[package] = recipe

    # Select new packages that are compiled and depend on a selected compiled package
    selection_modified = True
    while selection_modified:
        selection_modified = False
        for package, recipe in recipes.items():
            if package in selected_packages:
                continue
            if recipe["soma-forge"]["type"] == "compiled":
                for other_package in recipe["soma-forge"].get(
                    "internal-dependencies", []
                ):
                    if recipes[other_package]["soma-forge"]["type"] != "compiled":
                        continue
                    if other_package in selected_packages:
                        print(
                            f"Select {package} for building because {other_package} is selected"
                        )
                        selected_packages.add(package)
                        selection_modified = True

    # Generate rattler-build recipe and actions for selected packages
    actions = []
    for package, recipe in recipes.items():
        if package not in selected_packages:
            continue
        print(f"Generate recipe for {package}")
        if not force:
            src_errors = recipe["soma-forge"].get("src_errors")
            if src_errors:
                raise Exception(
                    f"Cannot build {package} because {', '.join(src_errors)}."
                )
        internal_dependencies = recipe["soma-forge"].get("internal-dependencies", [])
        if internal_dependencies:
            for dpackage in internal_dependencies:
                if all_packages[package]["type"] == "compiled" and all_packages[dpackage]["type"] == "compiled":
                    last_build_string = history.get(dpackage, {}).get("build_string")
                    if last_build_string and dpackage not in selected_packages:
                        build_string = last_build_string
                    else:
                        build_string = recipes[dpackage]['build']['string']
                    history
                    d = f"{dpackage}=={recipes[dpackage]['package']['version']}={build_string}"
                else:
                    d = f"{dpackage}=={recipes[dpackage]['package']['version']}"
                recipe.setdefault("requirements", {}).setdefault("run", []).append(d)

        changesets = src_errors = recipe["soma-forge"].get("changesets")

        # Force python version for soma package and interpreted packages
        if package == "soma" or recipe["soma-forge"].get("type") == "interpreted":
            recipe["requirements"]["run"].append(
                f"python=={build_info['options']['python']}"
            )

        # Remove soma-forge specific data
        recipe.pop("soma-forge", None)

        (plan / "recipes" / package).mkdir(exist_ok=True, parents=True)

        with open(plan / "recipes" / package / "recipe.yaml", "w") as f:
            yaml.safe_dump(recipe, f)

        actions.append(
            {"action": "create_package", "args": [package], "kwargs": {"test": test}}
        )
        if changesets:
            actions.append({"action": "set_changesets", "args": [package, changesets]})
    with open(plan / "actions.yaml", "w") as f:
        yaml.safe_dump(
            actions,
            f,
        )
