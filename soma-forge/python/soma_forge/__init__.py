import json
import os
import pathlib
import re
import shlex
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
