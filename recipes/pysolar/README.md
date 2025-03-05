# Create the pysolar package

Create the packages from the repos

**Note** Require ssh-key access to the repos: git@gitlab.com:brainomics/pysolar.git

```bash
mkdir /tmp/myroot /tmp/channel
cd /tmp/myroot
#
git clone https://github.com/neurospin/neuro-forge
# local install to get utils tools like neuro-forge swiss-knife
cd neuro-forge
pixi shell
pip install -e . # necessary to have the neuro-forge command in the PATH

neuro-forge build /tmp/channel pysolar
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
    ├── pysolar-8.4.2-pyh4616a5c_0.conda
    ├── repodata_from_packages.json
    └── repodata.json
```


Copy to the conda repos of NeuroSpin: **https://brainvisa.info/public**

```
# copy to the intermediate NS local repository
cp /tmp/channel/noarch/pysolar-8.4.2-pyh4616a5c_0.conda /drf/neuro-forge/public/noarch
# Public key to be registered before to run successfully this command
neuro-forge publish
```
