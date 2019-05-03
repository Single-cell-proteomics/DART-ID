DART-ID
=============

Intro
-----

The DART-ID code goal is to make the process as simple as possible. Run ```dart_id```, point it at the inputs, and expect an additional PEP_new column at the end. There are still some parameters that you will need to tweak manually as the default settings have not been fully generalized yet.

The bottom of this document contains links to an example configuration file and data that you can use to test the installation and performance of DART-ID.

# Installation

```
pip install git+https://github.com/SlavovLab/DART-ID
```

Uninstall the package with:

```
pip uninstall dart_id
```

The installation requires Python >= 3.4, < 3.7, and has been tested on Windows 8 / OSX Mojave 10.14 / Centos 7. Ubuntu/Linux instructions can be found in linux_install.md

## Install from source

We recommend using a [conda environment](https://conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html) to run DART-ID from source, so as to avoid any package versioning issues. You can create the same environment as us by using either the provided ```environment.yml``` spec or ```spec-file.txt``` (Mac OSX only). 

```
conda env create -f environment.yml -n dart && source activate dart
```

Then download the source code and run the provided shell script:

```
git clone https://github.com/SlavovLab/DART-ID
cd DART-ID
./dart_id.sh
```

Usage
----------

View parameters anytime yourself by typing "dart_id -h".

Input and output files are optional in the command line, and can be specified in the config file instead, if that's what you prefer.

An example config file, annotated and unannotated, can be found at ```example/config.yaml```

```
usage: dart_id [-h] [-i INPUT [INPUT ...]] [-o OUTPUT] [-v] [--version] -c
                 CONFIG_FILE

optional arguments:
  -h, --help            show this help message and exit
  -i INPUT [INPUT ...], --input INPUT [INPUT ...]
                        Input file(s) from search engine output (e.g.,
                        MaxQuant evidence.txt). Not required if input files
                        are specified in the config file
  -o OUTPUT, --output OUTPUT
                        Path to output folder
  -v, --verbose
  --version             Display the program's version
  -c CONFIG_FILE, --config-file CONFIG_FILE
                        Path to config file (required). See
                        example/config_example.yaml
```

Example runs
============

 
Test that your installation is working by running ```dart_id```.

An example configuration file can be downloaded from GitHub: [https://github.com/SlavovLab/DART-ID/blob/master/config_files/example_sqc_67_95_varied.yaml](https://github.com/SlavovLab/DART-ID/blob/master/config_files/example_sqc_67_95_varied.yaml).

The first few lines of the above configuration file specify the path to the input file:

```
## Input
## ==========================

input: 
  - /path/to/SQC_67_95_Varied/evidence.txt
```

You can download the ```evidence.txt``` file from MassIVE: [ftp://massive.ucsd.edu/MSV000083149/other/MaxQuant/SQC_67_95_Varied/evidence.txt](ftp://massive.ucsd.edu/MSV000083149/other/MaxQuant/SQC_67_95_Varied/evidence.txt). 

Then edit the path to the file downloaded, and run the following command:

```
dart_id -c config_files/example_sqc_67_95_varied.yaml -o ~/DART_ID/SQC_67_95_varied_20181206
```

An example analysis of the data and configuration file specified above is available publicly at [ftp://massive.ucsd.edu/MSV000083149/other/Alignments/SQC_varied_20180711_4/](ftp://massive.ucsd.edu/MSV000083149/other/Alignments/SQC_varied_20180711_4/). 


The current analysis heavily uses random number generation and cannot be directly compared. To compare the results of your analysis and the provided example analysis, download the folder above and inspect the ```figures.html``` report to compare results. We are working to affix the random number generation and improve the figures outputted to improve readability and reproducibility.
