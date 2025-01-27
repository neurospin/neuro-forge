import fnmatch
import git
import itertools
import json
import os
import pathlib
import rich
import re
import shlex
import shutil
import subprocess
import sys
import toml
import yaml

import click

from . import cli
from ..recipes import sorted_recipies

neuro_forge_url = "https://brainvisa.info/neuro-forge"


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
        return version

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
@click.option(
    "--publication-directory", type=click.Path(), default="/drf/neuro-forge/public"
)
@click.argument("pixi_directory", type=click.Path())
@click.argument("packages", type=str, nargs=-1)
def packaging_plan(pixi_directory, publication_directory, packages, force, test=True):
    if not publication_directory or publication_directory.lower() == "none":
        publication_directory = None
    else:
        publication_directory = pathlib.Path(publication_directory).absolute()
    if publication_directory is not None and not publication_directory.exists():
        raise RuntimeError(
            f"Publication directory {publication_directory} does not exist"
        )

    if not packages:
        packages = ["*"]
    selector = re.compile("|".join(f"(?:{fnmatch.translate(i)})" for i in packages))

    # pixi_root contains the base Pixi environment used for building software from sources
    pixi_root = pathlib.Path(pixi_directory).absolute()
    # the plan directory contains all files to generate and apply packaging plan
    plan_dir = pixi_root / "plan"

    # Check if a plan file already exists and can be erased
    history_file = plan_dir / "history.json"
    if plan_dir.exists():
        if history_file.exists() and not force:
            raise RuntimeError(
                f"A plan already exists in {plan_dir} and was used. Erase it or use --force option"
            )
        print(f"Erasing existing plan: {plan_dir}")
        shutil.rmtree(plan_dir)
    plan_dir.mkdir()

    # Read build information
    build_info_file = pixi_root / "conf" / "build_info.json"
    with open(build_info_file) as f:
        build_info = json.load(f)

    # Get the release history for selected environment (e.g.
    # environment="6.0") from the publication directory
    release_history = {}
    if publication_directory is not None:
        release_history_file = (
            publication_directory / f"soma-env-{build_info['environment']}.json"
        )
        if release_history_file.exists():
            with open(release_history_file) as f:
                release_history = json.load(f)

    # Set the new environment full version by incrementing last published version patch
    # number or setting it to 0
    environment_version = release_history.get("environment_version")
    if environment_version:
        # Increment patch number
        version, patch = environment_version.rsplit(".", 1)
        patch = int(patch) + 1
        environment_version = f"{version}.{patch}"
    else:
        environment_version = f"{build_info['environment']}.0"
    development_environment = environment_version.startswith("0.")

    # Next environment is used to build dependencies strings for components:
    #   >={environment},<{next_environment}
    next_environment = build_info["environment"].split(".")
    next_environment[-1] = str(int(next_environment[-1]) + 1)
    next_environment = ".".join(next_environment)

    # List of actions stored in the plan file
    actions = []

    recipes = {}
    all_packages = build_info["all_packages"]
    selected_packages = set()
    # Get ordered selection of recipes. Order is based on package
    # dependencies. Recipes are selected according to user selection and
    # modification since last packaging
    for recipe in sorted_recipies():
        package = recipe["package"]["name"]
        if package not in all_packages:
            print(f"Skip package {package} (not in build tree)")
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
            if changesets != release_history.get(package, {}).get("changesets"):
                print(
                    f"Select {package} for building because detected changes in source"
                )
                selected_packages.add(package)
            else:
                print(f"No change detected in package {package}")

            # Write build section in recipe
            recipe.setdefault("build", {})["string"] = build_info["build_string"]
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
                    "  make install-\\${component}-test",
                    "done",
                    "END",
                )
            )

            # Set package version in recipe
            recipe["package"]["version"] = package_version
            # Save information in recipe because we do not know yet
            # if package will be selected for building. It will be known
            # later when dependencies are resolved.
            recipe["soma-forge"]["src_errors"] = src_errors
            recipe["soma-forge"]["changesets"] = changesets
        elif recipe["soma-forge"]["type"] == "virtual":
            recipe["package"]["version"] = environment_version
            recipe.setdefault("build", {})["string"] = build_info["build_string"]
            print(
                f"Select virtual package {package} {environment_version} for building"
            )
            selected_packages.add(package)
        else:
            raise Exception(
                f"Invalid recipe for {package} (bad type or no component defined)"
            )
        recipes[package] = recipe

    # Select new packages that are compiled and depend on, at least, one selected compiled package
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

    # Generate rattler-build recipe and action for soma-env package
    print(f"Generate recipe for soma-env {environment_version}")
    (plan_dir / "recipes" / "soma-env").mkdir(exist_ok=True, parents=True)
    with open(plan_dir / "recipes" / "soma-env" / "recipe.yaml", "w") as f:
        yaml.safe_dump(
            {
                "package": {"name": "soma-env", "version": environment_version},
                "build": {
                    "string": build_info["build_string"],
                    "script": (
                        "mkdir --parents $PREFIX/share/soma\n"
                        f"echo '{environment_version}' > soma-env.version"
                    ),
                },
                "requirements": {"run": [f"python=={build_info['options']['python']}"]},
            },
            f,
        )

    commit_actions = []

    # Generate rattler-build recipe and actions for selected packages
    package_actions = []
    for package, recipe in recipes.items():
        if package not in selected_packages:
            continue
        print(f"Generate recipe for {package} {recipe["package"]["version"]}")
        if not force:
            src_errors = recipe["soma-forge"].get("src_errors")
            if src_errors:
                raise Exception(
                    f"Cannot build {package} because {', '.join(src_errors)}."
                )
        internal_dependencies = recipe["soma-forge"].get("internal-dependencies", [])
        if internal_dependencies:
            for dpackage in internal_dependencies:
                d = f"{dpackage}>={recipes[dpackage]['package']['version']}"
                recipe.setdefault("requirements", {}).setdefault("run", []).append(d)

        changesets = src_errors = recipe["soma-forge"].get("changesets")

        # Add dependency to soma-env package
        recipe["requirements"]["run"].append(
            f"soma-env>={environment_version},<{next_environment}"
        )

        # Check if a version_change is necessary
        published_version = tuple(
            int(i)
            for i in release_history.get(package, {}).get("version", "0").split(".")
        )
        package_version = tuple(int(i) for i in recipe["package"]["version"].split("."))
        if not development_environment and published_version == package_version:
            new_version = package_version[:-1] + (package_version[-1] + 1,)
            component = recipe["soma-forge"]["components"][0]
            # Find file to change
            src = pixi_root / "src" / component
            file = src / "project_info.cmake"
            if file.exists():
                version_regexps = (
                    re.compile(
                        r"(\bset\s*\(\s*BRAINVISA_PACKAGE_VERSION_MAJOR\s*)"
                        r"([0-9]+)(\s*\))",
                        re.IGNORECASE,
                    ),
                    re.compile(
                        r"(\bset\s*\(\s*BRAINVISA_PACKAGE_VERSION_MINOR\s*)"
                        r"([0-9]+)(\s*\))",
                        re.IGNORECASE,
                    ),
                    re.compile(
                        r"(\bset\s*\(\s*BRAINVISA_PACKAGE_VERSION_PATCH\s*)"
                        r"([0-9]+)(\s*\))",
                        re.IGNORECASE,
                    ),
                )
            else:
                file_format = "python"
                version_regexps = (
                    re.compile(r"(\bversion_major\s*=\s*)([0-9]+)(\b)"),
                    re.compile(r"(\bversion_minor\s*=\s*)([0-9]+)(\b)"),
                    re.compile(r"(\bversion_micro\s*=\s*)([0-9]+)(\b)"),
                )
                if not file.exists():
                    files = list(
                        itertools.chain(
                            src.glob("info.py"),
                            src.glob("*/info.py"),
                            src.glob("python/*/info.py"),
                        )
                    )
                    if not files:
                        raise RuntimeError(
                            f"Cannot find component version file (info.py or project_info.cmake) in {src}"
                        )
                    file = files[0]
            with open(file) as f:
                file_contents = f.read()
            for regex, version_component in zip(version_regexps, new_version):
                file_contents, _ = regex.subn(
                    f"\\g<1>{version_component:d}\\g<3>", file_contents
                )
            actions.append(
                {
                    "action": "modify_file",
                    "kwargs": {
                        "file": str(file),
                        "file_contents": file_contents,
                    },
                }
            )

            commit_actions.append(
                {
                    "action": "git_commit",
                    "kwargs": {
                        "repo": str(src),
                        "modified": [str(file)],
                        "message": f"Set Conda package {package} to version {'.'.join(str(i) for i in new_version)}",
                    },
                }
            )

        # Remove soma-forge specific data from recipe
        recipe.pop("soma-forge", None)

        (plan_dir / "recipes" / package).mkdir(exist_ok=True, parents=True)

        with open(plan_dir / "recipes" / package / "recipe.yaml", "w") as f:
            yaml.safe_dump(recipe, f)

        package_actions.append(
            {"action": "create_package", "args": [package], "kwargs": {"test": test}}
        )

        release_history.setdefault(package, {})["changesets"] = changesets
        build_string = recipe.get("build", {}).get("string")
        release_history[package]["build_string"] = build_string
        release_history[package]["version"] = recipe["package"]["version"]

    if commit_actions:
        actions.extend(commit_actions)
        actions.append({"action": "rebuild"})
    else:
        # Add an action to assess that compilation was successfully done
        actions.extend((
            {
                "action": "check_build_status",
            },
            {
                "action": "create_package",
                "args": ["soma-env"],
                "kwargs": {"test": False},
            },
        ))

        actions.extend(package_actions)
        release_history["environment_version"] = environment_version
        packages_dir = pixi_root / "plan" / "packages"
        if publication_directory is not None:
            actions.append(
                {
                    "action": "publish",
                    "kwargs": {
                        "environment": build_info["environment"],
                        "packages_dir": str(packages_dir),
                        "packages": ["soma-env"] + list(selected_packages),
                        "release_history": release_history,
                        "publication_dir": str(publication_directory),
                    },
                }
            )

    with open(plan_dir / "actions.yaml", "w") as f:
        yaml.safe_dump(
            actions,
            f,
        )

    if commit_actions:
        console = rich.console.Console()
        console.print(
            "Source code modification requires version changes. Verify the "
            "plan and apply it to change project versions. Then build and "
            "apply another plan for packaging.",
            style="bold red",
        )
