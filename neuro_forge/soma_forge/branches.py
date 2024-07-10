import copy
from pathlib import Path
import yaml

"""
Define the link between soma-forge global branch and the location
of the source of each brainvisa-cmake components.
"""

_branches_info = None


def rupdate(target, source):
    if target is not None and isinstance(source, dict):
        for k, v in source.items():
            target[k] = rupdate(target.get(k), v)
        return target
    return source


def branches_info():
    global _branches_info

    if _branches_info is None:
        with open(Path(__file__).parent / "branches_info.yaml") as f:
            _branches_info = {}
            infos = yaml.safe_load(f)
            # Resolve branches inheritance
            while infos:
                for branch, branch_info in infos.items():
                    base = branch_info.get("base")
                    if base and base in _branches_info:
                        fusioned_info = copy.deepcopy(_branches_info[base])
                        rupdate(fusioned_info, branch_info)
                        del fusioned_info["base"]
                        _branches_info[branch] = fusioned_info
                        break
                    elif not base:
                        _branches_info[branch] = branch_info
                        break
                else:
                    raise ValueError(
                        f"Invalid dependencies declared in {Path(__file__).parent / "branches_info.yaml"}"
                    )
                del infos[branch]
    return _branches_info


def branch_info(branch):
    result = branches_info().get(branch)
    if result is None:
        raise KeyError(
            f"{branch} is not a valid branch. Possible values are {', '.join(iter_branches())}."
        )
    return result


def iter_branches():
    """Iterate over all defined global branches"""
    return branches_info().keys()


def iter_components():
    """Iterate over all defined component names"""
    return branches_info()["dev"]["components"].keys()


def component_source(component, soma_forge_branch):
    """Return a git source location given component and global branch name.
    The result is a dictionary containing the followign items:
        - "url": Git URL containing the sources
        - "branch" (optional): git branch
    """
    branch_info = branches_info().get(soma_forge_branch)
    if not branch_info:
        raise ValueError(f"Unknown branch: {soma_forge_branch}")
    result = branch_info.get("components", {}).get(component)
    if not result:
        return None
    default_branch = result.get("default_branch", branch_info.get("default_branch"))
    branch = result.get("branch", branch_info.get("branch", default_branch))
    if branch and "branch" not in result:
        result = result.copy()
        result["branch"] = branch
        result.pop("default_branch", None)
    else:
        raise ValueError(
            f"No branch defined for component {component} in soma-forge branch {soma_forge_branch}"
        )
    return (result["url"], result["branch"])


if __name__ == "__main__":
    for branch in iter_branches():
        for component in iter_components():
            print(component, branch)
            print(component_source(component, branch))
    from pprint import pprint

    pprint(branches_info())
