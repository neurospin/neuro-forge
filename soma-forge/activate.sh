export CASA="$PIXI_PROJECT_ROOT"
export CASA_BRANCH="master"
export CASA_CONF="$CASA/conf"
export CASA_SRC="$CASA/src"
export CASA_BUILD="$CASA/build"
export CASA_TEST="$CASA/tests"
export PATH="$CASA/src/brainvisa-cmake/bin:$CASA/build/bin:$PATH:$CONDA_PREFIX/x86_64-conda-linux-gnu/sysroot/usr/bin"
export CMAKE_LIBRARY_PATH="$CONDA_PREFIX/lib:$CONDA_PREFIX/x86_64-conda-linux-gnu/sysroot/usr/lib64"
export BRAINVISA_BVMAKER_CFG="$CASA/conf/bv_maker.cfg"
export LD_LIBRARY_PATH="$CASA/build/lib:$LD_LIBRARY_PATH:$CONDA_PREFIX/x86_64-conda-linux-gnu/sysroot/usr/lib64"
python_short=$(python -c 'import sys; print(".".join(str(i) for i in sys.version_info[0:2]))')
export PYTHONPATH="$CASA/src/brainvisa-cmake/python:$CASA/build/lib/python${python_short}/site-packages:$PYTHONPATH"
export BRAINVISA_TEST_REF_DATA_DIR="$CASA_TEST/ref"
export BRAINVISA_TEST_RUN_DATA_DIR="$CASA_TEST/test"
