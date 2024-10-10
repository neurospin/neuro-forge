# neuro-forge: reproducible provisioning of neuroimaging workspaces for image processing and data analysis

This project contains everything needed to build and update the neuro-forge packages. neuro-forge is a set of packages for the Conda ecosystem dedicated to image analysis and data analysis in neuroimaging. The URL for neuro-forge channel is https://brainvisa.info/neuro-forge.

neuro-forge is still in early alpha stage and should only be used for testing.

## Prerequisite
Most action with neuro-forge requires to [install Pixi](https://pixi.sh). Pixi is a package manager fully compatible with Conda packages ecosystem but, at the time of this writing, much more efficient than Conda.

# How to create a workspace directory and install neuro-forge packages

neuro-forge packages are contained in a Conda channel located in https://brainvisa.info/neuro-forge. They can be installed using [Pixi](https://pixi.sh), [Mamba](https://mamba.readthedocs.io) or [Conda](https://docs.conda.io). We recommend the use of pixi. For instance, once pixi is installed, one can use the following script to setup a workspace containing anatomist:

```
# Create a workspace directory
mkdir ~/workspace

# Setup workspace
cd ~/workspace
pixi init -c https://brainvisa.info/neuro-forge -c conda-forge

# Enter workspace
pixi shell

# Install anatomist
pixi add anatomist

# Run anatomist
anatomist
```

# How to create packages for neuro-forge channel

Neuro-forge is currently maintained by [Neurospin GAIA team](https://neurospin.github.io/gaia/). The only way to add/modify/remove a package from [neuro-forge channel](https://brainvisa.info/neuro-forge) is to modify the neuro-forge channel directory which is a clone of the published channel located in Neurospin. Modification to this directory is allowed to packages maintainer. The neuro-forge channel directory is synchronized to [neuro-forge channel](https://brainvisa.info/neuro-forge) when modified.

If you wish to participate to neuro-forge, you can contact [the BrainVISA team](mailto:admin@brainvisa.info).

## Package creation

The creation of packages for neuro-forge is based on the use of [rattler-build](https://prefix-dev.github.io/rattler-build). Each package is created by writing a recipe that is used by rattler-build to create the final package file. The neuro-forge channel is composed of three kinds of recipes:

- [Standard recipes](https://github.com/neurospin/neuro-forge/tree/main/recipes) that are standard rattler-build recipes that are git compatible (i.e. composed of, at most, a few text file) and can be built independently using only dependencies from standard channels such as conda-forge and bioconda.
- Internal recipes that are located in the neuro-forge directory in Neurospin. Packages are put here either because they are too big (some packages requires several giga bytes of data) or because the recipe is not public.
- [soma-forge recipes](https://github.com/neurospin/neuro-forge/tree/main/soma-forge) that are used to create packages for the [BrainVISA](https://brainvisa.info) project. Most of these packages are compiled ; that adds a binary dependency between them. Therefore their compilation and packaging requires a soma-forge development environment.
- Internal recipes are located in a directory in Neurospin and are not directly accessible. These recipes require either too many data to be put on git or are subject to a software licence and cannot be distributed.


# Use standard recipes

In order to build packages from standard recipes, the `neuro-forge build` command can be used. To setup an environment for this command, one can use `git` and `pixi` with the following script:

```
git clone https://github.com/neurospin/neuro-forge
cd neuro-forge
pixi shell
pip install -e . # necessary to have the neuro-forge command in the PATH
```

Then, one or more packages can be built by using the following command.
```
neuro-forge build {output directory} {package} [{package}...]
```

For instance, to build a package for the latest `ldscore` release:
```
neuro-forge build /tmp/channel ldscore
```

# How to create a soma-forge development workspace

First install soma-forge command that is located in neuro-forge project.
```
git clone https://github.com/neurospin/neuro-forge
cd neuro-forge
pixi run python -m pip install -e .
```

Then create the BrainVISA development directory by giving its location and the environment version, plus optionally a list of target packages. Environment version is `0.0` for standard development using default git branches, `0.1` for development with Capsul 3 or `6.0` for the compilation of `brainvisa-6.0` branches. Target packages are the name of soma-forge packages. It will select all corresponding brainvisa-cmake components (taking into account packages dependencies) and put them in `bv_maker.cfg` file. By default, a selection of packages defined specifically for the environment will be included.
```
pixi run soma-forge init /somewhere/soma-forge-0.0 0.0
```

Finally, the development directory can be used independently of neuroforge:
```
cd /somewhere/soma-forge-0.0
pixi shell
bv_maker
```

## soma-forge packages

The packages currently built have the following dependencies:
- green: package containing brainvisa-cmake components ;
- olive: empty package with dependencies ;
- bisque: neuro-forge base package ; 
- light blue: package from conda-forge.

![dependencies](https://github.com/brainvisa/soma-forge/assets/3062350/c34edacd-ec27-49b4-b68d-75505390d63b)
