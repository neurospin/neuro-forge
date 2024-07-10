from pathlib import Path
import yaml

"""
Define the link between soma-forge global branch and the location
of the source of each brainvisa-cmake components.
"""

_branches_info = None


def branches_info():
    global _branches_info

    if _branches_info is None:
        with open(Path(__file__).parent / "branches_info.yaml") as f:
            _branches_info = yaml.safe_load(f)
    return _branches_info


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
    result = {}
    default_branch = None
    while branch_info:
        if not default_branch and "branch" in branch_info:
            default_branch = branch_info["branch"]
        component_info = branch_info.get("components", {}).get(component)
        if component_info:
            for k, v in component_info.items():
                if k not in result:
                    result[k] = v
        base_branch = branch_info.get("base")
        if base_branch:
            branch_info = branches_info()[base_branch]
        else:
            branch_info = None
    if default_branch and "branch" not in result:
        result["branch"] = default_branch
    return result


if __name__ == "__main__":
    for branch in iter_branches():
        for component in iter_components():
            print(component, branch)
            print(component_source(component, branch))
