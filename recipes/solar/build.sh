# the binary release is obtained unzipped
# unzip solar-eclipse-8.4.2-static-Linux.zip
# got to the solar842 working dir
cd solar842

# use solar842 dir as temporary
#    - fix LANG to avoid instaltion error message
#    - fix LANG to avoid run time error related tot LANG
#    - no worry about messages: install_solar: 83: [: -a: unexpected operator

mkdir $PREFIX/solar-8.4.2 $PREFIX/bin
LANG=/usr/lib/locale/en_US
export LANG
sh install_solar $PREFIX/solar-8.4.2 $PREFIX/bin
sed -i -f <(cat << 'EOF'
2i LANG=/usr/lib/locale/en_US
2i export LANG
EOF
) $PREFIX/bin/solar
