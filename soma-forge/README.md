# Soma-forge

Development and packaging environment for packages that depends on soma, the C++/Python ecosystem of [BrainVISA](https://brainvisa.info) project.

## Prerequisite
Whatever you want to do with soma-forge, you must first [install Pixi](https://pixi.sh). It is a binary without dependency to put somewhere in the PATH. If you want to avoid the use of the script proposed by Pixi team (that install in `~/.pixi/bin` and changes `~/.bashrc`), you can download the latest release of `pixi`executable for Linux x86_64 achitecture with the following command:

```
curl -fsSL https://github.com/prefix-dev/pixi/releases/latest/download/pixi-x86_64-unknown-linux-musl.tar.gz | tar zx
```

## Test soma-forge packages

Soma-orge packages are hosted in neuro-forge channel and can be tested by [installing a neuro-forge workspace](https://github.com/neurospin/neuro-forge/tree/main?tab=readme-ov-file#how-to-create-a-workspace-and-install-neuro-forge-packages).

## soma-forge packages

The packages currently built have the following dependencies:
- green: package containing brainvisa-cmake components ;
- olive: empty package with dependencies ;
- bisque: neuro-forge base package ; 
- light blue: package from conda-forge.

![dependencies](https://github.com/brainvisa/soma-forge/assets/3062350/c34edacd-ec27-49b4-b68d-75505390d63b)

## Setup a soma-forge development workspace

A soma-forge development workspace is a [neuro-forge workspace](https://github.com/neurospin/neuro-forge/tree/main?tab=readme-ov-file#how-to-install-and-use-neuro-forge-packages) where the `soma-forge` package is installed and configured. It can be setup with the following script:

```
# Clone neuro-forge to create workspace directory
git clone https://github.com/neurospin/neuro-forge ~/workspace

# Setup workspace
cd ~/workspace
pixi run soma-forge setup
```

If https://brainvisa.info/neuro-forge is not available, a local directory can be used. Such a directory [can be created using neuro-forge](https://github.com/neurospin/neuro-forge/tree/main?tab=readme-ov-file#how-to-create-neuro-forge-channel).

Once the development workspace is configured, `bv_maker` can be used directly from within the workspace and built programs are in the PATH and ready to be used.

## Create soma-forge packages

<html>
<!--
Conda packages installed via pixi (as dependencies) are found in the `.pixi` sub-directory in the soma-forge directory.

If one needs to make packages, use the following command:

```
pixi run forge --no-test
```

If not already done, this runs `pixi run build` that executes `bv_maker` and creates a `build/success` file when all steps (except sources) are successful. Then it creates non existing packages for all internal or external software. By default, packages are only created when tests are successful but some packages (such as `soma` that contains Aims) need some reference data for testing therefore I recommend to skip tests with `--no-test` until a procedure is created to generate these data.
--!>
</html>

