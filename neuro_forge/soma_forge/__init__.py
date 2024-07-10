# import click
# import fnmatch
# import git
# import itertools
# import json
# import os
# import pathlib
# import re
# import shlex
# import shutil
# import subprocess
# import sys
# import toml
# import yaml



# def test_ref():
#     test_ref_data_dir = os.environ.get("BRAINVISA_TEST_REF_DATA_DIR")
#     if not test_ref_data_dir:
#         print("No value for BRAINVISA_TEST_REF_DATA_DIR", file=sys.stderr, flush=True)
#         return 1
#     os.makedirs(test_ref_data_dir, exists_ok=True)


# def test(name):
#     test_commands = get_test_commands()
#     if name is None:
#         print(", ".join(test_commands))
#     else:
#         test_run_data_dir = os.environ.get("BRAINVISA_TEST_RUN_DATA_DIR")
#         if not test_run_data_dir:
#             print(
#                 "No value for BRAINVISA_TEST_RUN_DATA_DIR", file=sys.stderr, flush=True
#             )
#             return 1
#         os.makedirs(test_run_data_dir, exists_ok=True)

#         commands = test_commands.get(name)
#         if commands is None:
#             print("ERROR: No test named", name, file=sys.stderr, flush=True)
#             return 1
#         for command in commands:
#             try:
#                 subprocess.check_call(command, shell=True)
#             except subprocess.CalledProcessError:
#                 print(
#                     "ERROR command failed:",
#                     command,
#                     file=sys.stderr,
#                     flush=True,
#                 )
#                 return 1


# def dot(packages, conda):
#     conda_forge = set()
#     print("digraph {")
#     print("  node [shape=box, color=black, style=filled]")
#     for recipe in selected_recipes(packages):
#         package = recipe["package"]["name"]
#         if recipe["soma-forge"]["type"] == "brainvisa-cmake":
#             print(f'  "{package}" [fillcolor="aquamarine"]')
#         elif recipe["soma-forge"]["type"] == "virtual":
#             print(f'  "{package}" [fillcolor="darkolivegreen2"]')
#         else:
#             print(f'  "{package}" [fillcolor="bisque"]')
#         for dependency in (
#             recipe["soma-forge"].get("requirements", {}).get("brainvisa-cmake", [])
#         ):
#             print(f'  "{package}" -> "{dependency}"')
#         for dependency in (
#             recipe["soma-forge"].get("requirements", {}).get("soma-forge", [])
#         ):
#             print(f'  "{package}" -> "{dependency}"')
#         if conda:
#             for dependency in (
#                 recipe["soma-forge"].get("requirements", {}).get("conda-forge", [])
#             ):
#                 conda_forge.add(dependency)
#                 print(f'  "{package}" -> "{dependency}"')
#     for package in conda_forge:
#         print(f'  "{package}" [fillcolor="aliceblue"]')
#     print("}")


# def main():
#     parser = argparse.ArgumentParser(
#         prog="python -m soma_forge",
#     )

#     subparsers = parser.add_subparsers(
#         required=True,
#         title="subcommands",
#     )

#     parser_setup = subparsers.add_parser("setup", help="setup environment")
#     parser_setup.set_defaults(func=setup)
#     parser_build = subparsers.add_parser(
#         "build", help="get sources, compile and build brainvisa-cmake components"
#     )
#     parser_build.set_defaults(func=build)

#     parser_forge = subparsers.add_parser("forge", help="create conda packages")
#     parser_forge.set_defaults(func=forge)
#     parser_forge.add_argument(
#         "-f",
#         "--force",
#         action="store_true",
#         help="build selected packages even it they exists",
#     )
#     parser_forge.add_argument(
#         "--no-test",
#         dest="test",
#         action="store_false",
#         help="do not run tests while building packages",
#     )
#     parser_forge.add_argument(
#         "-s",
#         "--show",
#         action="store_true",
#         help="do not build packages, only show the ones that are selected",
#     )
#     parser_forge.add_argument(
#         "packages",
#         type=str,
#         nargs="*",
#         help="select packages using their names or Unix shell-like patterns",
#     )
#     parser_test = subparsers.add_parser("test", help="manage brainvisa-cmake tests")
#     parser_test.add_argument(
#         "name",
#         type=str,
#         nargs="?",
#         default=None,
#         help="name of the test to run. No value just list the possible names.",
#     )
#     parser_test.set_defaults(func=test)

#     parser_dot = subparsers.add_parser(
#         "dot", help="create a graphviz dot file showing packages dependencies"
#     )
#     parser_dot.add_argument(
#         "-c",
#         "--conda",
#         action="store_true",
#         help="include conda-forge packages",
#     )
#     parser_dot.add_argument(
#         "packages",
#         type=str,
#         nargs="*",
#         help="select packages using their names or Unix shell-like patterns",
#     )
#     parser_dot.set_defaults(func=dot)

#     args = parser.parse_args(sys.argv[1:])
#     kwargs = vars(args).copy()
#     del kwargs["func"]
#     sys.exit(args.func(**kwargs))
