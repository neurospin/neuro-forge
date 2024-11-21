# MLUKB an environment to reproduce UKB ML paper

This description is for rattler-build / pixi / conda / logics.

## The paper
Population modeling with machine learning can enhancemeasures of mental health. (2021). Kamalaker Dadi, Gaël Varoquaux, Josselin Houenou, Danilo Bzdok, Bertrand Thirion, Denis Engemann.


## How to generate the environment.

### Clone the neuro-forge repos

Install locally the helpers (eg the rattler-build command...)

```bash
mkdir /tmp/myroot
cd /tmp/myroot
git clone https://github.com/neurospin/neuro-forge
cd neuro-forge
pixi shell
pip install -e . 
```

### Now build the mlukb environment

The conda package is created in ./output. 
 - Suppose the channel is CHANNEL. 
 - copy the locally produced conda package in it
 - refresh (re-index) the channel CHANNEL

```bash
# create the package
cd recipes/mlukb
rattler-build build --recipe recipe.yaml
tree output            # see the package

# copy to the main channel
export CHANNEL=/neurospin/brainomics/ig_channel
cp output/noarch/mlukb-*.conda $CHANNEL/noarch

# re-index the main repo
/usr/bin/env conda index $CHANNEL
```

### Install the MLUKB env on a fresh host/system
Use pixi to create MYENV
```bash
cd /tmp
export MYENV=myenv
pixi init -c file://$CHANNEL -c conda-forge -c bioconda $MYENV
cd /tmp/$MYENV
pixi shell
pixi add mlukb
```

## Build a movable env

A two step process.

### Use the conda-pack 
```bash
cd /tmp
export MYENV=myenv
cd /tmp/$MYENV
pixi shell
pixi add conda-pack
# pack the (base) env of pixi
conda-pack --output $MYENV.tar.gz
```

### Get from the non connected HCP system/host

```bash
cd /tmp/$MYENV
scp $MYENV.tar.gz USER@irene-fr.ccc.cea.fr:/XX/commons/xportenv/
mkdir $MYENV
tar -xzf $MYENV.tar.gz -C $MYENV

# step1
cd $MYENV
source bin/activate
conda-unpack
source bin/deactivate

# step2 use module
cd ..
mkdir -p /XX/Modules/modulefiles/myenv
module sh-to-mod bash /XX/commons/xportenv/myenv/bin/activate > /XX/Modules/modulefiles/myenv/0.1

# try it
# boot a fresh shell
module avail my*
module load myenv
```
