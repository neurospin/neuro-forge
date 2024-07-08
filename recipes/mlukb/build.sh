python -m pip install -t "$PREFIX" --no-deps --no-build-isolation --force-reinstall "$SRC_DIR"
mkdir "$PREFIX/site-packages"
mv $PREFIX/mlukb* $PREFIX/site-packages
for i in $PREFIX/bin/*; do
    sed -i '1s:.*:#!/usr/bin/env python:' $i
done
