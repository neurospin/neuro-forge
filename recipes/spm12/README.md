# Create the spm12 package

Find more information in the [Standalone SPM](https://www.fil.ion.ucl.ac.uk/spm/docs/installation/standalone/) documentation.

The binaries are available starting from the [Download SPM](https://www.fil.ion.ucl.ac.uk/spm/software/download/) page.

Initial SPM Standalone binary packages used to be built against MATLAB R2010a and depended on the associated MATLAB Runtime 7.13. Unfortunately, that obsolete version of the MATLAB Runtime is not compatible with recent Linux distributions. We had to jump through hoops to run SPM12 on recent Linux machines, running SPM Standalone against MATLAB Runtime 9.7, associated to MATLAB R2019b, hoping for compatibility both with recent operating systems and the obsolete SPM Standalone binary package:
* [issue to open SPM8 standalone and SPM12 standalone with the latest singularity image](https://github.com/brainvisa/casa-distro/issues/268)

Nowadays, FIL provide multiple versions of the latest release 7771 of SPM12, each for a specific version of the MATLAB Runtime:

| SPM12 Standalone 7771 package  | MATLAB Runtime version |
| ------------------------------ | ---------------------- |
| `spm12_r7771_R2010a.zip`       | MATLAB Runtime 7.13    |
| `spm12_r7771_Linux_R2015b.zip` | MATLAB Runtime 9.0     |
| `spm12_r7771_Linux_R2016a.zip` | MATLAB Runtime 9.0.1   |
| `spm12_r7771_Linux_R2016b.zip` | MATLAB Runtime 9.1     |
| `spm12_r7771_Linux_R2017a.zip` | MATLAB Runtime 9.2     |
| `spm12_r7771_Linux_R2017b.zip` | MATLAB Runtime 9.3     |
| `spm12_r7771_Linux_R2018a.zip` | MATLAB Runtime 9.4     |
| `spm12_r7771_Linux_R2018b.zip` | MATLAB Runtime 9.5     |
| `spm12_r7771_Linux_R2019a.zip` | MATLAB Runtime 9.6     |
| `spm12_r7771_Linux_R2019b.zip` | MATLAB Runtime 9.7     |
| `spm12_r7771_Linux_R2020a.zip` | MATLAB Runtime 9.8     |
| `spm12_r7771_Linux_R2020b.zip` | MATLAB Runtime 9.9     |
| `spm12_r7771_Linux_R2021a.zip` | MATLAB Runtime 9.10    |
| `spm12_r7771_Linux_R2021b.zip` | MATLAB Runtime 9.11    |
| `spm12_r7771_Linux_R2022a.zip` | MATLAB Runtime 9.12    |
| `spm12_r7771_Linux_R2022b.zip` | MATLAB Runtime 9.13    |

For now, I'm depending on MATLAB Runtime Version 9.7, but that's obviously not satisfactory.
