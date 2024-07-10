import click
from . import cli
from ..pixi import read_pixi_config, write_pixi_config
from ..recipes import selected_recipes


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
@click.option("-v", "--verbose", is_flag=True)
@click.option("--show", is_flag=True)
@click.option("--force", is_flag=True)
@click.option("--test", type=bool, default=True)
@click.argument("directory", type=click.Path())
@click.argument("packages", type=str, nargs=-1)
def dev_packages_plan(directory, packages, force, show, test=True, verbose=None):
    if show and verbose is None:
        verbose = True
    if verbose is True:
        verbose = sys.stdout
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

    channels = read_pixi_config(pixi_root)["project"]["channels"]
    forge = pixi_root / "forge"
    recipes = {}
    for recipe in sorted_recipies():
        package = recipe["package"]["name"]
        print(package)
        if not selector.match(package):
            continue
        components = recipe["soma-forge"].get("components", [])
        if components:
            # Check that build tree is clean
            version = None
            for component in components:
                src = pixi_root / "src" / component
                if version is None:
                    version = brainvisa_cmake_component_version(src)
                repo = git.Repo(src)
                if not force and repo.is_dirty():
                    raise Exception(f"Repository {src} contains uncomited files")
                if not force and repo.untracked_files:
                    raise Exception(f"Repository {src} has local modifications")
            recipe["package"]["version"] = version
        elif recipe["soma-forge"]["type"] == "virtual":
            # TODO
            continue
        else:
            raise Exception(f"No components defined in {package} recipe")

        recipe.setdefault("build", {})["number"] = build_number
        recipe["build"][
            "string"
        ] = f"{build_info['build_string']}_{build_info['build_number']}"
        recipe["build"]["script"] = "\n".join(
            (
                'cd "$PIXI_PROJECT_ROOT"',
                "pixi run bash << END",
                'cd "$CASA_BUILD"',
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

        recipes[package] = recipe

    for package, recipe in recipes.items():
        internal_dependencies = recipe["soma-forge"].get("internal-dependencies", [])
        if internal_dependencies:
            recipe.setdefault("requirements", {}).setdefault("run", []).extend(
                internal_dependencies
            )

        # Remove soma-forge specific data
        recipe.pop("soma-forge", None)

        (forge / "recipes" / package).mkdir(exist_ok=True, parents=True)

        with open(forge / "recipes" / package / "recipe.yaml", "w") as f:
            yaml.safe_dump(recipe, f)

        # if not show:
        #     build_dir = forge / "bld" / f"rattler-build_{package}"
        #     if build_dir.exists():
        #         shutil.rmtree(build_dir)
        #     internal_recipe = read_recipe(package)
        #     internal_recipe.pop("internal-dependencies", None)
        #     command = [
        #         "rattler-build",
        #         "build",
        #         "--experimental",
        #         "--no-build-id",
        #         "-r",
        #         recipe_dir,
        #         "--output-dir",
        #         str(forge),
        #     ]
        #     if not test:
        #         command.append("--no-test")
        #     for i in channels + [f"file://{str(forge)}"]:
        #         command.extend(["-c", i])
        #     try:
        #         subprocess.check_call(command)
        #     except subprocess.CalledProcessError:
        #         print(
        #             "ERROR command failed:",
        #             " ".join(f"'{i}'" for i in command),
        #             file=sys.stderr,
        #             flush=True,
        #         )
        #         return 1
