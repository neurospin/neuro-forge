export PKG_CONFIG_PATH=${CONDA_PREFIX}/x86_64-conda-linux-gnu/sysroot/usr/share/pkgconfig:${CONDA_PREFIX}/lib/pkgconfig:"$PKG_CONFIG_PATH"
export ACLOCAL_PATH=$CONDA_PREFIX/x86_64-conda-linux-gnu/sysroot/usr/share/aclocal:"$ACLOCAL_PATH"
export CPPFLAGS="-isystem ${CONDA_PREFIX}/include -isystem ${CONDA_PREFIX}/x86_64-conda-linux-gnu/sysroot/usr/include"
# export CPPFLAGS="-isystem /volatile/riviere/casa-distro/conda/brainvisa-6.0/src/neuro-forge/.pixi/envs/default/include"
./autogen.sh
./configure --prefix=$PREFIX
echo CPPFLAGS: $CPPFLAGS
make -j -k
make VERBOSE=1
make install
