# Create the solar package

Create the packages from the NITRC repos to produce a conda package

```bash
mkdir /tmp/myroot /tmp/channel
cd /tmp/myroot
#
git clone https://github.com/neurospin/neuro-forge
# local install to get utils tools like neuro-forge swiss-knife
cd neuro-forge
pixi shell
pip install -e . # necessary to have the neuro-forge command in the PATH

neuro-forge build /tmp/channel solar
```
List the output of the process

```
tree /tmp/channel/
/tmp/channel/
├── linux-64
│   ├── current_repodata.json
│   ├── index.html
│   ├── repodata_from_packages.json
│   └── repodata.json
└── noarch
    ├── current_repodata.json
    ├── index.html
    ├── ldscore-2.0.1-pyh4616a5c_0.conda
    ├── repodata_from_packages.json
    └── repodata.json
```

Copy to the conda repos of NeuroSpin : **https://brainvisa.info/public**

```
# copy to the intermediate NS local repository
cp /tmp/channel/linux-64/solar-8.4.2-hb0f4dca_0.conda /drf/neuro-forge/public/linux-64
# Public key to be registered before to run succesfully this command
neuro-forge publish
```