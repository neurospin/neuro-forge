import copy
from pathlib import Path

import yaml

"""
Definition of soma-forge environments and their links with
the location of the source of each brainvisa-cmake components.
"""

_environments_info = None


def rupdate(target, source):
    if target is not None and isinstance(source, dict):
        for k, v in source.items():
            target[k] = rupdate(target.get(k), v)
        return target
    return source


def environments_info():
    global _environments_info

    if _environments_info is None:
        with open(Path(__file__).parent / "environments_info.yaml") as f:
            _environments_info = {}
            infos = yaml.safe_load(f)
            # Resolve environments inheritance
            while infos:
                for environment, environment_info in infos.items():
                    base = environment_info.get("base")
                    if base and base in _environments_info:
                        fusioned_info = copy.deepcopy(_environments_info[base])
                        rupdate(fusioned_info, environment_info)
                        del fusioned_info["base"]
                        _environments_info[environment] = fusioned_info
                        break
                    elif not base:
                        _environments_info[environment] = environment_info
                        break
                else:
                    raise ValueError(
                        f"Invalid dependencies declared in {Path(__file__).parent / 'environments_info.yaml'}"
                    )
                del infos[environment]
    return _environments_info


def get_environment_info(environment):
    result = environments_info().get(environment)
    if result is None:
        raise KeyError(
            f"{environment} is not a valid environment. Possible values are {', '.join(iter_environments())}."
        )
    return result


def iter_environments():
    """Iterate over all defined global environments"""
    return environments_info().keys()


def iter_components():
    """Iterate over all defined component names"""
    return environments_info()["6.0"]["components"].keys()


def component_source(component, environment):
    """Return a git source location given component and environment name.
    The result is a dictionary containing the following items:
        - "url": Git URL containing the sources
        - "branch" (optional): git branch
    """
    environment_info = environments_info().get(environment)
    if not environment_info:
        raise ValueError(f"Unknown environment: {environment}")
    result = environment_info.get("components", {}).get(component)
    if not result:
        return None
    default_branch = result.get(
        "default_branch", environment_info.get("default_branch")
    )
    branch = result.get("branch", environment_info.get("branch", default_branch))
    if branch and "branch" not in result:
        result = result.copy()
        result["branch"] = branch
        result.pop("default_branch", None)
    else:
        raise ValueError(
            f"No branch defined for component {component} in environment {environment}"
        )
    return (result["url"], result["branch"])


if __name__ == "__main__":
    for environment in iter_environments():
        for component in iter_components():
            print(component, environment)
            print(component_source(component, environment))
    from pprint import pprint

    pprint(environments_info())
