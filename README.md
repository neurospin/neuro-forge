# neuro-forge: reproducible provisioning of neuroimaging workspaces for image processing and data analysis

This project contains everything needed to build and update the neuro-forge packages. neuro-forge is a set of packages for the Conda ecosystem dedicated to image analysis and data analysis in neuroimaging.

neuro-forge is still in early alpha stage and should only be used for testing.

## Prerequisite
Most action with neuro-forge requires to [install Pixi](https://pixi.sh). It is a binary without dependency to put somewhere in the PATH. If you want to avoid the use of the script proposed by Pixi team (that install in `~/.pixi/bin` and changes `~/.bashrc`), you can download the latest release of `pixi`executable for Linux x86_64 achitecture with the following command:

```
curl -fsSL https://github.com/prefix-dev/pixi/releases/latest/download/pixi-x86_64-unknown-linux-musl.tar.gz | tar zx
```

## How to create a workspace directory and install neuro-forge packages

neuro-forge packages are contained in a Conda channel located in https://brainvisa.info/neuro-forge (this is a temporary URL, it may change at any moment). They can be installed using [Pixi](https://pixi.sh), [Mamba](https://mamba.readthedocs.io) or [Conda](https://docs.conda.io). We recommand the use of pixi. For instance, once pixi is installed, one can use the following script to setup a workspace containing anatomist:

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

## How to create packages for neuro-forge channel

The creation of packages for neuro-forge is based on the use of [rattler-build](https://prefix-dev.github.io/rattler-build). The neuro-forge channel is composed of two kinds of packages:

- [Standard packages](https://github.com/neurospin/neuro-forge/tree/main/recipes) that are standard rattler-build recipes that can be built independently using only dependencies from standard channels such as conda-forge and bioconda.
- [soma-forge packages](https://github.com/neurospin/neuro-forge/tree/main/soma-forge) that are packages from the [BrainVISA](https://brainvisa.info) project and requires a soma-forge development environement to be build.


In order to build standard packages, the `neuro-forge build` command can be used. To setup an environment for this command, one can use `git` and `pixi` with the following script:

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

## How to create a soma-forge development workspace

First install soma-forge command that is located in neuro-forge project.
```
git clone https://github.com/neurospin/neuro-forge
cd neuro-forge
git checkout rolling-release
pixi run python -m pip install -e recipes/soma-forge
```

Then create the BrainVISA development directory by giving its location and the target packages. Target packages are the name of soma-forge packages. It will select all corresponding brainvisa-cmake components (taking into account pakages dependencies) and put them in `bv_maker.cfg` file. By default, all known packages are included including ones that had not been tested at all and will make compilation fail. Options can be given to select some build options : python version, Qt major version and Capsul major version.
```
pixi run soma-forge init /somewhere/brainvisa-py3.11-cap2-qt5 brainvisa cortical-surface morphologist-baby constellation
```

Finally, the development directory can be used independently of neuroforge:
```
cd /somewhere/brainvisa-py3.11-cap2-qt5
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
