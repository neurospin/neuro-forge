# echo PKG_CONFIG_PATH: ${PKG_CONFIG_PATH}
export PKG_CONFIG_PATH=${CONDA_PREFIX}/lib/pkgconfig
MESA_VERSION=24.3.3
MESA_FILENAME=mesa-${MESA_VERSION}.tar.xz
MESA_SHA256SUM=105afc00a4496fa4d29da74e227085544919ec7c86bd92b0b6e7fcc32c7125f4
tmp=${SRC_DIR}
cd "$tmp"
wget "https://archive.mesa3d.org/$MESA_FILENAME"
if ! [ "$(sha256sum "$MESA_FILENAME")" = "$MESA_SHA256SUM  $MESA_FILENAME" ];
then
    echo "ERROR: checksum of $MESA_FILENAME does not match." 2>&1
    exit 1
fi
tar -Jxf "$MESA_FILENAME"
cd mesa-"$MESA_VERSION"
mkdir build
cd build
meson setup \
    --prefix $PREFIX/mesalib \
    --libdir lib \
    -D gallium-drivers=swrast \
    -D platforms=x11 \
    -D vulkan-drivers= \
    -D buildtype=release \
    -D glx=xlib
    # -D glx=dri \
    # -D glvnd=enabled
ninja
ninja install
