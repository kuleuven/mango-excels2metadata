import pandas as pd
import os.path
from pathlib import Path
from irods.session import iRODSSession
from irods.meta import iRODSMeta, AVUOperation
from irods.exception import DataObjectDoesNotExist, CollectionDoesNotExist
from irods.data_object import iRODSDataObject
from collections.abc import Generator


# region OpenExcel
def create_file_object(path: str, session=None):
    """Turn path to file into a file-like object.

    Args:
        session: (iRODSSession or None): session to connect to iRODS.
            Session can be set to None for testing non-irods functionalities.
        path (str): Path to tabular file

    Raises:
        FileNotFoundError: If the file cannot be found locally or in ManGO.

    Returns:
        pathlib.Path or irods.iRODSDataObject: File-like object to read metadata from.
    """
    ppath = Path(path)
    if ppath.suffix not in [".xlsx", ".csv", ".tsv"]:
        raise IOError("Filetype not accepted")
    if ppath.exists():
        return ppath
    if session:
        return session.data_objects.get(path)
    raise FileNotFoundError


def parse_tabular_file(path: str, session=None, separator: str = ","):
    """Parse tabular file.

    Args:
        path (str): Path to the tabular file.
        session (iRODSSession or None): session to connect to iRODS.
            If it is none, it is assumed that we are testing
        separator (str, optional): Separator for plain text files.. Defaults to ",".

    Raises:
        IOError: If the file cannot be parsed (it is not .xlsx, .csv or .tsv) it won't be read.

    Returns:
        dict: Dictionary of pandas.DataFrames with sheet names as keys.
    """

    file = create_file_object(path, session)
    if path.endswith("xlsx"):
        # Local excel files are binary and should be opened with 'rb'.
        # However, iRODS implemented their 'open' method differently,
        # and there you should use just 'r' instead
        reading_mode = "r" if type(file) == iRODSDataObject else "rb"
        with file.open(reading_mode) as f:
            return pd.read_excel(f, sheet_name=None)
    else:
        # these types are not binary and should be opened with 'r'
        with file.open("r") as f:
            return {"single_sheet": pd.read_csv(f, sep=separator)}


# endregion
# region Preprocessing


# Will this survive as it is??
def extract_filename(tabulardata, path_prefix=""):
    """Extract filename from the tabular data.
    This is the default method to extract the full path of the data object
    to which metadata will be added from tabular data.

    Args:
        tabulardata (pandas.Series): Row of the dataframe with metadata to add.
        path_prefix (str, optional): Initial part of the absolute path of the data object, which should be added in
        case of a relative path in the tabulardata. Defaults to "".

    Yields:
        str: Absolute path(s) to the data objects
    """
    final_path = Path(path_prefix) / Path(tabulardata["dataobject"])
    if final_path.is_absolute() and final_path.parts[2] != "home":
        raise IOError(
            "Invalid filename: if the path is absolute, the second collection should be 'home'."
        )
    yield str(final_path)


# endregion
# region Core


def dict_to_avus(row: dict) -> Generator[iRODSMeta]:
    """Convert a dictionary of metadata name-value pairs into a generator of iRODSMeta"""
    avus = (iRODSMeta(str(key), str(value)) for key, value in row.items())
    return avus


def generate_rows(dataframe: pd.DataFrame) -> Generator[tuple]:
    """Yield a tuple of filename and metadata-dictionary from a dataframe"""
    for _, row in dataframe.iterrows():
        yield (row["filename"], {k: v for k, v in row.items() if k != "filename"})


def apply_metadata_to_data_object(path: str, avu_dict: dict, session: iRODSSession):
    """Add metadata from a dictionary to a given data object"""
    obj = session.data_objects.get(path)
    obj.metadata.apply_atomic_operations(
        *[AVUOperation(operation="add", avu=item) for item in dict_to_avus(avu_dict)]
    )


# endregion

# region Chains


# These are the functions that would be called from the command line :)
# (and use click)
def do_something():
    return


# endregion

if __name__ == "__main__":
    try:
        env_file = os.environ["IRODS_ENVIRONMENT_FILE"]
    except KeyError:
        env_file = os.path.expanduser("~/.irods/irods_environment.json")

    ssl_settings = {}
    with iRODSSession(irods_env_file=env_file, **ssl_settings) as session:
        do_something()
