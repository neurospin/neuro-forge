# neuro-forge: provisioning of neuroimaging workspace for image processing and data analysis

This project contains everything you need to build and update the neuro-forge packages. neuro-forge is a set of packages for the Conda ecosystem dedicated to image analysis and data analysis in neuroimaging.

# How to install and use neuro-forge packages
neuro-forge packages are contained in a Conda channel located in https://brainvisa.info/neuro-forge. They can be installed using [Pixi](https://pixi.sh), [Mamba](https://mamba.readthedocs.io) or [Conda](https://docs.conda.io). We recommand the use of pixi. For instance, once pixi is install, one can use the following script to setup a workspace containing anatomist:

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

# How to create neuro-forge channel

The creation of a packages for neuro-forge is based on the use of [rattler-build](https://prefix-dev.github.io/rattler-build). The neuro-forge channel is composed of two kind of packages:

- Base packages that are standard rattler-build recipes that can be build independently using only dependencies from conda-forge.
- soma-forge packages that are packages from the [BrainVISA](https://brainvisa.info) project and requires a soma-forge development environement to be build.

