# Olive Importer

## Purpose

Import the data from Olive OCR XML files into a canonical JSON format defined by the Impresso project.

## Input data

A sample of the input data for this script can be found in [sample_data/](sample_data/) (data for Gazette de Lausanne (GDL), Feb 2-5 1900).

## Usage

Run the script sequentially:

    python olive_importer.py --input-dir=sample_data/ --output-dir=out/ --temp-dir=tmp/ --verbose --log-file=import_test.log

or in parallel:

    python olive_importer.py --input-dir=sample_data/ --output-dir=out/ --temp-dir=tmp/ --verbose --log-file=import_test.log --parallelize

For further info about the usage, see:

    python olive_importer.py --help

## Notes

- the JSON schemas implemented here are provisional, and should just serve as the basis for discussion

## TODO

- [ ] define and implement `page.json` schema
- [ ] revise and implement the `info.json` schema
- [x] deal with `<QW>` elements when extracting box coordinates

## JSON Schemas

The output of this script is a bunch of JSON files.

TODO: update with schema examples (when finalised)