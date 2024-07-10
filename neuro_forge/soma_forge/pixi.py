import toml

def read_pixi_config(pixi_root):
    """
    Read pixi.toml file
    """
    with open(pixi_root / "pixi.toml") as f:
        return toml.load(f)


def write_pixi_config(pixi_root, pixi_config):
    """
    wite pixi.toml file
    """
    with open(pixi_root / "pixi.toml", "w") as f:
        toml.dump(pixi_config, f, encoder=toml.TomlPreserveCommentEncoder())
