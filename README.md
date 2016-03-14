# svdconv

## Purpose
Svdconv script converts Keil *.svd peripheral description files to files for use with GCC. 

Script generates:
* header with definition of types, that describe peripheral registers as set of bitfields
* source file with declaration of peripheral registers, each register is mapped to own section
* GNU linkres script file with sections placed in proper address in memory

## Requirements
Requires python3

## Usage
`svdconv.py file.svd`
