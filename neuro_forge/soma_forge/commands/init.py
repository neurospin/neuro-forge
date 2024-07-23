import click
import git
import itertools
import json
import pathlib
import shutil
import subprocess
import sys

from rich.table import Table
from rich.pretty import Pretty

from . import cli, console
from ..pixi import read_pixi_config, write_pixi_config
from ..recipes import selected_recipes
from ..environments import component_source, get_environment_info

default_python = "3.11"
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


@cli.command()
@click.option(
    "-p",
    "--python",
    type=click.Choice(["3.10", "3.11", "3.12"]),
    default=None,
    help=f"Python version (default=config file value or {default_python})",
)
@click.option("--force", is_flag=True)
@click.argument("directory", type=click.Path())
@click.argument("environment", type=str)
@click.argument("packages", type=str, nargs=-1)
def init(directory, environment, packages, python, force):
    """Create or reconfigure a full BrainVISA development directory"""
    environment_info = get_environment_info(environment)
    neuro_forge_url = "https://brainvisa.info/neuro-forge"
    pixi_root = pathlib.Path(directory).absolute()
    if not (pixi_root / "pixi.toml").exists():
        pixi_root.mkdir(exist_ok=True)
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

    build_info_file = conf_dir / "build_info.json"
    packages = packages or environment_info.get("default_packages") or "all"
    build_info = {
        "environment": environment,
        "packages": packages,
        "options": {
            "python": default_python,
        },
    }
    if build_info_file.exists() and not force:
        with open(build_info_file) as f:
            current_build_info = json.load(f)
        build_info = current_build_info.copy()
    for name in (
        "python",
        "capsul",
        "qt",
    ):
        v = locals().get(name)
        if v:
            build_info["options"][name] = v

    build_info["build_string"] = f"py{build_info['options']['python'].replace('.', '')}"

    if force or not build_info_file.exists():
        with open(build_info_file, "w") as f:
            json.dump(build_info, f, indent=4)
    else:
        with open(build_info_file) as f:
            current_build_info = json.load(f)
        if current_build_info != build_info and build_dir.exists():
            console.print(
                f"[red]Existing build options in [bold]{build_info_file}[/bold] differs from the selected ones[/red]"
            )
            table = Table()
            table.add_column("existing options")
            table.add_column("selected options")
            table.add_row(Pretty(current_build_info), Pretty(build_info))
            console.print(table)
            console.print(
                f"Either remove the directory [code]{build_dir}[/code] or use [code]--force[/code] option."
            )
            sys.exit(1)
        with open(build_info_file, "w") as f:
            json.dump(build_info, f, indent=4)

    packages = build_info["packages"]
    pixi_config = read_pixi_config(pixi_root)
    pixi_project_name = f"soma-build-{environment}-{build_info['build_string']}"
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
    all_packages = {}
    for recipe in selected_recipes(packages or ["all"]):
        package = recipe["package"]["name"]
        print(package, recipe["soma-forge"]["type"])
        all_packages[package] = {"type": recipe["soma-forge"]["type"]}
        for component in recipe["soma-forge"].get("components", []):
            source = component_source(component, environment)
            if not source:
                raise ValueError(
                    f"Cannot find source for component {component} in environment {environment}"
                )
            components.setdefault(package, {})[component] = source
            print("   ", component, source[0], source[1])
        requirements = recipe.get("requirements", {}).get("run", []) + recipe.get(
            "requirements", {}
        ).get("build", [])
        if requirements:
            print("   ", "\n    ".join(f"-> {i}" for i in requirements))
        print()
        for requirement in requirements:
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

    # Store all_packages in build_info.json
    with open(build_info_file) as f:
        bi = json.load(f)
    bi["all_packages"] = all_packages
    with open(build_info_file, "w") as f:
        json.dump(bi, f, indent=4)

    # Generate bv_maker.cfg
    components_source = ["brainvisa brainvisa-cmake master"]
    components_build = []
    for package, cb in components.items():
        components_source.append(f"# Components of package {package}")
        components_build.append(f"# Components of package {package}")
        for component, source in cb.items():
            url, branch = source
            components_source.append(f"git {url} {branch} {component}")
            components_build.append(f"brainvisa {component} * $CASA_SRC")
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

    environment_dependencies = environment_info["build-dependencies"].copy()
    environment_dependencies["python"] = f"== {build_info['options']['python']}"

    # Add dependencies to pixi.toml
    for package, constraint in itertools.chain(
        environment_dependencies.items(), dependencies.items()
    ):
        pixi_constraint = pixi_config.get("dependencies", {}).get(package)
        if pixi_constraint is not None:
            if pixi_constraint == "*":
                pixi_constraint = set()
            else:
                pixi_constraint = set(pixi_constraint.split(","))
            if constraint == "*":
                constraint = set()
            elif isinstance(constraint, str):
                constraint = {constraint}
            constraint.update(pixi_constraint)
            if pixi_constraint != constraint:
                del pixi_config["dependencies"][package]
                modified = True
            else:
                continue
        if constraint:
            if isinstance(constraint, str):
                constraint = constraint.split(",")
            pixi_config.setdefault("dependencies", {})[package] = ",".join(constraint)
        else:
            pixi_config.setdefault("dependencies", {})[package] = "*"

    shutil.copy(
        pathlib.Path(__file__).parent.parent / "activate.sh",
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
