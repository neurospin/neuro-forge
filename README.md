# neuro-forge: reproducible provisioning of neuroimaging workspaces for image processing and data analysis

This project contains everything needed to build and update the neuro-forge packages. neuro-forge is a set of packages for the Conda ecosystem dedicated to image analysis and data analysis in neuroimaging.

## How to create a workspace and install neuro-forge packages

neuro-forge is still in early alpha stage and should only be used for testing.

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

## How to create neuro-forge channel

The creation of packages for neuro-forge is based on the use of [rattler-build](https://prefix-dev.github.io/rattler-build). The neuro-forge channel is composed of two kinds of packages:

- [Base packages](https://github.com/neurospin/neuro-forge/tree/main/recipes) that are standard rattler-build recipes that can be built independently using only dependencies from conda-forge.
- [soma-forge packages](https://github.com/neurospin/neuro-forge/tree/main/soma-forge) that are packages from the [BrainVISA](https://brainvisa.info) project and requires a soma-forge development environement to be build.


In order to build a neuro-forge channel from scratch, one must use pixi. The following script will create a `channel` directory containing the base packages that are necessary to complement conda-forge in order to build other packages.

```
git clone https://github.com/neurospin/neuro-forge
cd neuro-forge
pixi run neuro-forge init channel
```

## How to create a BrainVISA development directory with soma-forge

First install soma-forge command that is located in neuro-forge project.
```
git clone https://github.com/neurospin/neuro-forge
cd neuro-forge
pixi run python -m pip install -e recipes/soma-forge
```

Then create the BrainVISA development directory by giving its location and the target packages. Target packages are the name of soma-forge packages. It will select all corresponding brainvisa-cmake components (taking into account pakages dependencies) and put them in `bv_maker.cfg` file. Options can be given to select some build options : python version, Qt major version and Capsul major version.
```
soma-forge init /somewhere/brainvisa-py3.11-cap2-qt5 brainvisa
```

Finally, the development directory can be used independently of neuroforge:
```
cd /somewhere/brainvisa-py3.11-cap2-qt5
pixi shell
bv_maker
```
