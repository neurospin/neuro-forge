import shutil
import subprocess
import sys

import requests

package = sys.argv[1]
version = sys.argv[2]
dest = sys.argv[3]

url = "https://conda.anaconda.org/conda-forge/linux-64/repodata.json"
print(f'Reading {url}')
r = requests.get(url)
r.raise_for_status()
j = r.json()
s=sorted(((k,v) for k, v in j["packages.conda"].items() if v["name"] == package and v["version"] == version), key=lambda x: x[1].get("timestamp"))
if not s:
    raise FileNotFoundError(f"Cannot find {package}=={version} on conda-forge")
file_name = s[-1][0]
url = f"https://conda.anaconda.org/conda-forge/linux-64/{file_name}"
print(f'Downloading {url}')
r = requests.get(url)
r.raise_for_status()
with open(s[-1][0], mode="wb") as f:
    f.write(r.content)
print(f"Uncompress {file_name}")
subprocess.check_call(['cph', 'x', '--dest', dest, file_name])
shutil.rmtree(f"{dest}/info")
