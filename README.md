# Python module to extract metadata from tables

Some ManGO users have expressed their wish to upload metadata of some data objects or collections as Excel (or at least tabular) files that could then be parsed and added as AVUs. This was already implemented for the Hackathon and it's being implemented for the Dayr-al Barsha project, but these implementations are also tailored to the specific needs/standards of those projects. Other users are also interested, mainly because they already add/have the metadata in tabular format and adding it manually would be extra work.

For that reason, we want to create a Python module that:

- identifies a csv/Excel in a given collection
- identifies the reference to the target data objects or collections in that tabular file
    + By default, we would expect one column with the name
    + We would allow custom functions to override this default, for example by combining different columns
- for each data object or colleciton (=row in the tabular file) it extracts all relevant metadata pairs (name of a column + value) and adds the metadata with atomic operations
    + By default, all columns would be parsed and their original names would be used
    + It would be possible to map the names to modified names
    + It would be possible to filter out the columns and validate the values, especially via a metadata schema

This would be a MVP level output: basic and configurable enough to address the needs of different projects. But it should be possible to integrate this with project-specific needs, such as the date parsing from filenames in the Dayr-al Barsha project.

Of course, this module should include docstrings and unit testing :)
