# Create the neuro-forge package

Create the packages from the repos

```bash
mkdir /tmp/myroot /tmp/channel
cd /tmp/myroot
#
git clone https://github.com/neurospin/neuro-forge
# local install to get utils tools like neuro-forge swiss-knife
cd neuro-forge
pixi shell
pip install -e . # necessary to have the neuro-forge command in the PATH

neuro-forge build /tmp/channel neuro-forge
```
List the output of the process

```
tree /tmp/channel/
├── linux-64
│   ├── current_repodata.json
│   ├── index.html
│   ├── repodata_from_packages.json
│   └── repodata.json
└── noarch
    ├── current_repodata.json
    ├── index.html
    ├── neuro-forge-1.0.0-pyh4616a5c_0.conda
    ├── repodata_from_packages.json
    └── repodata.json
```


Copy to the conda repos of NeuroSpin: **https://brainvisa.info/public**

```
# copy to the intermediate NS local repository
cp /tmp/channel/noarch/neuro-forge-1.0.0-pyh4616a5c_0.conda /drf/neuro-forge/public/noarch
neuro-forge publish
```
