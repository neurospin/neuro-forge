import git


def iter_tags(url):
    return (
        i.rsplit("/", 1)[-1]
        for i in git.cmd.Git().ls_remote(url, tags=True).split("\n")
        if not i.endswith("^{}")
    )


def iter_branches(url):
    return (
        i.rsplit("/", 1)[-1]
        for i in git.cmd.Git().ls_remote(url, heads=True).split("\n")
    )
