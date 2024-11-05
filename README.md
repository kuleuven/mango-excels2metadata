# Python module to extract metadata from tables

Use this module to process tabular files in which each row represents an iRODS data object
and each column contains either an identifier or metadata to add to this data object.
It supports plain text files and Excel files, which could be stored locally or in iRODS itself.

As always, create a virtual environment and install the dependencies described in the [requirements file](./requirements.txt):

```sh
python -m venv venv
. venv/bin/activate
pip install -r requirements.txt
```

## Usage

This module can run on the command line with two commands: `setup` and `run`.

The `setup` command takes as arguments the path to a tabular file (local or in iRODS) and
the desired path for the output YAML, asks the user questions about how to
parse the tabular file, and outputs a configuration file.

This configuration file can then be provided as the `--config` option to the `run`
command in order to standardize tabular files and properly obtain paths to data objects
and attach metadata to them based on the columns of these files.

## `setup`

The configuration file can be created as follows:

```sh
python metadata_from_tabular.py filename output_path
```

In this case `filename` is the path to a tabular file (csv, tsv, Excel...),
stored either locally or in iRODS. If it lives in iRODS, the `--irods` flag should be used,
so that an iRODS session is started:

```sh
python metadata_from_tabular.py /zone/home/project/path/to/tabular output_path --irods
```

If the tabular file is a plain text file, it is possible to specify a column separator
with the `--sep` option, which has "," as a default:

```sh
python metadata_from_tabular.py testdata/testdata.csv test-output.yml --sep ";"
```

If the file can be found and opened as a dataframe, the user will be prompted with questions
that will later guide preprocessing of equivalent tabular files:

- If there are multiple sheets in an Excel file, which one(s) should be used?
- Which of the columns contains a unique identifier of the data objects that metadata has to be attached to?
- If the unique identifier is not an absolute path, is it a relative path or part of filename?
And if so, within which collection should the data objects be found?
- Should any columns be whitelisted or blacklisted?

The final YAML will be printed on the console and saved as a file locally

## `run`

Given a path to a tabular file with metadata and a YAML with the settings to preprocess it,
metadata can be added with the `run` command:

```sh
python metadata_from_tabular.py path_to_tabular --config path/to/config.yml
```

For testing purposes, it is possible to use
the `--dry-run` flag, which simulates the preprocessing and identification of metadata and
prints a small report at the end.
An iRODS session will be initiated always.


```sh
python metadata_from_tabular.py path_to_tabular --config path/to/config.yml --dry-run
```

## Examples

### A small csv file

```sh
python metadata_from_tabular.py setup testdata/testdata.csv test-config.yaml --sep ";"
python metadata_from_tabular.py run testdata/testdata.csv --config test-config.yaml --dry-run
```

### A larger Excel file with multiple sheets

```sh
python metadata_from_tabular.py setup testdata/bigger-testdata.xlsx bigger-test-config.yaml
python metadata_from_tabular.py run testdata/bigger-testdata.xlsx --config bigger--config.yaml --dry-run
```

## Actual test data

```sh
python metadata_from_tabular.py setup testdata/metadata.tsv testdata/voetlab-training.yaml --sep "\t"
python metadata_from_tabular.py run testdata/metadata.tsv --config voetlab-training.yaml
```
