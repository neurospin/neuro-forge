# ig-forge

Entry points for the maintenance of the customized packages of interest in imaging-genetics.

- [ig-forge](#ig-forge)
  - [Prerequisites](#prerequisites)
  - [The packages](#the-packages)
    - [ns-ldscore](#ns-ldscore)

## Prerequisites

Have Pixi (see above) and rattler-build installed.
```bash
# the dir where neuro-forge is cloned
GITFORGE=/<MYPATH>/NF/neuro-forge/ig-forge

# working pathes
MINE=/<MYPATH>/mine
CHANNEL=/<MYPATH>/channel

# let's go to the mine
cd ${MINE}
#
pixi init -c conda-forge
# 
pixi add rattler-build
```
We are ready to create customized packages...

## The packages
### ns-ldscore
Currently the source code retrieval from pipy is not scripted here. The code is available from the git (a patched copy) : see ldsc-2.0.1

```
cd ${MINE}
pixi shell
rattler-build build \
             -r ${GITFORGE}/ns-ldscore/recipe/recipe.yaml \
             --output-dir ${CHANNEL}
```