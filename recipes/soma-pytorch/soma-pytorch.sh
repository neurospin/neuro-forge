#!/bin/sh
PYTHON_VERSION=`python -c 'import sys; print("%d.%d" % sys.version_info[:2])'`
if [ ! -e "$CONDA_PREFIX/soma-override/lib/python$PYTHON_VERSION/site-packages/torch" ]; then
    python -m pip install --prefix "$CONDA_PREFIX/soma-override" --force-reinstall --no-deps torch torchvision
    python -m pip install --prefix "$CONDA_PREFIX/soma-override" torch torchvision
fi

python_dir="$CONDA_PREFIX/soma-override/lib/python$PYTHON_VERSION/site-packages"

first_pythonpath_component=$(printf '%s\n' "$PYTHONPATH" | cut -d: -f1)

if [ "$first_pythonpath_component" != "$python_dir" ]; then
    export PYTHONPATH="$python_dir:$PYTHONPATH"
fi
