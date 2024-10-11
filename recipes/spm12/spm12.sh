#!/bin/sh

# https://github.com/spm/spm-docker/blob/main/matlab/singularity.def
export MCR_INHIBIT_CTF_LOCK=1
export SPM_HTML_BROWSER=0

# Start a new interactive shell for SPM12
exec "${CONDA_PREFIX}/spm12/run_spm12.sh" "${CONDA_PREFIX}/MATLAB/MATLAB_Runtime/v97" ${1+"\$@"}
