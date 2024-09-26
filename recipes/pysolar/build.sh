python -m pip install -t "$PREFIX" --no-deps --no-build-isolation --force-reinstall "$SRC_DIR"
mkdir "$PREFIX/site-packages"
mv $PREFIX/pysolar* $PREFIX/site-packages
sed -i s+/neurospin/brainomics/ig_applis/bin/solar+$PREFIX/bin $PREFIX/site-packages/pysolar/info.py
for i in $PREFIX/bin/*; do
    sed -i '1s:.*:#!/usr/bin/env python:' $i
done