# MLUKB an environment to reproduce Kamalaker's paper

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
```bash
cd recipes/mlukb
rattler-build build --recipe recipe.yaml

```