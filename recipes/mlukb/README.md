# MLUKB an environment to reproduce UKB ML paper

This description is for rattler-build / pixi / conda / logics.

## The paper
Population modeling with machine learning can enhancemeasures of mental health. (2021). Kamalaker Dadi, Gaël Varoquaux, Josselin Houenou, Danilo Bzdok, Bertrand Thirion, Denis Engemann.


## How to generate the environement.

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

### Now build the mlukb environement

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
pixi add conda-build # to get the conda-index cmd
/usr/bin/env conda index $CHANNEL
```

### Install the MLUKB env on a fresh host/system
Use pixi to create MYENV
```bash
export MYENV=myenv
cd /tmp
pixi init -c file://$CHANNEL -c bioconda -c conda-forge $MYENV
cd /tmp/$MYENV
pixi shell
pixi add mlukb
```

