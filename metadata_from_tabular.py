import pandas as pd
import os.path
from pathlib import Path
from irods.session import iRODSSession
from irods.meta import iRODSMeta, AVUOperation
from irods.exception import DataObjectDoesNotExist, CollectionDoesNotExist
from irods.data_object import iRODSDataObject
from irods.column import Criterion
from irods.models import Collection, DataObject
from collections.abc import Generator
import click
from rich.prompt import Prompt, Confirm
from rich.console import Console
from rich.markdown import Markdown
from rich.pretty import pprint


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


def search_objects_with_identifier(session, workingdirectory, identifier, exact_match):
    """Searches a given project for objects starting with a certain identifier


    Arguments
    ---------
    session: obj
        An iRODSSession object

    workingdirectory: str
        Path to the collection in iRODS

    identifier: str
        The identifier you want to search for

    Returns
    -------
    paths: str
        A list of data object paths matching the identifier
    """

    operator = "=" if exact_match else "like"
    query = (
        session.query(DataObject.name, Collection.name)
        .filter(Criterion("like", Collection.name, workingdirectory + "%"))
        .filter(Criterion(operator, DataObject.name, identifier + "%"))
    )
    paths = [f"{result[Collection.name]}/{result[DataObject.name]}" for result in query]
    return paths


def query_dataobjects_with_filename(
    session, df, filename_column, workingdirectory, exact_match=True
):
    """
    Queries data objects in iRODS based on identifiers in the dataframe,
    and creates a row for each result with the accompanying metadata.
    """

    new_rows = []
    for index, identifier in enumerate(df[filename_column]):
        paths = search_objects_with_identifier(
            session, workingdirectory, identifier, exact_match
        )
        for path in paths:
            new_row = df.iloc[index]
            new_row["dataobject"] = path
            # create a 1 row dataframe, which needs to be transposed (hence the T)
            new_rows.append(new_row.to_frame().T)
    if len(new_rows) > 0:
        new_df = pd.concat(new_rows, ignore_index=True)
    else:
        columns = [column for column in df.columns]
        columns.append("dataobject")
        new_df = pd.DataFrame(columns=columns)
    return new_df


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
        yield (row["dataobject"], {k: v for k, v in row.items() if k != "dataobject"})


def apply_metadata_to_data_object(path: str, avu_dict: dict, session: iRODSSession):
    """Add metadata from a dictionary to a given data object"""
    obj = session.data_objects.get(path)
    obj.metadata.apply_atomic_operations(
        *[AVUOperation(operation="add", avu=item) for item in dict_to_avus(avu_dict)]
    )


# endregion

# region prompts

console = Console()


def explain_multiple_choice():
    console.print(
        "Type one answer at a time, pressing Enter afterwards. Press Enter twice when you are done.",
        style="italic magenta",
    )


def select_sheets(sheet_collection: dict) -> list:
    selection_of_sheets = list(sheet_collection.keys())
    if len(sheet_collection) == 1:
        if selection_of_sheets[0] == "single_sheet":
            console.print(
                "You have provided a plain text file, no multiple sheets, great work!"
            )
        else:
            console.print(
                Markdown(
                    f"The file you provided has only one sheet: `{selection_of_sheets[0]}`."
                )
            )
        return selection_of_sheets[0]
    all_sheets = Confirm.ask("Would you like to use all of the available sheets?")
    if all_sheets:
        return selection_of_sheets
    explain_multiple_choice()
    selected_sheets = []
    while True:
        selected_sheet = Prompt.ask(
            "Which of the available sheets would you like to select?",
            choices=selection_of_sheets + [""],
        )
        if selected_sheet:
            selected_sheets.append(selected_sheet)
        else:
            break
    return selected_sheets


def identify_dataobject_column(sheet_collection: dict) -> str:
    columns = set([col for sheet in sheet_collection.values() for col in sheet.columns])
    dfs = "dataframe has" if len(sheet_collection) == 1 else "dataframes have"
    cols = "1 column" if len(columns) == 1 else f"{len(columns)} columns"
    column_intro = f"Your {dfs} {cols}:\n\n"
    column_list = "\n\n".join(f"- {col}" for col in columns)
    console.print(Markdown(column_intro + column_list))
    return Prompt.ask(
        "Which column contains an unique identifier for the target data object?",
        choices=columns,
    )


def classify_dataobject_column(dataobject_column: str) -> dict:
    import re

    path_type = Prompt.ask(
        f"Is the path coded in `{dataobject_column}` a relative path or part of a filename?",
        choices=["relative", "part"],
    )
    workdir = ""
    while not re.match("/[a-z_]+/home/[^/]+/", workdir):
        workdir = Prompt.ask(
            "What is the absolute path of the collection where we can find these data objects? (It should start with `/{zone}/home/{project}/...`)"
        )
    if path_type == "relative":
        console.print(
            Markdown(
                f"Great! The relative paths in `{dataobject_column}` will be chained to `{workdir}`!"
            )
        )
    else:
        console.print(
            Markdown(
                f"Great! Data objects will be found by querying the contents of `{dataobject_column}` within `{workdir}`!"
            )
        )
    return {"path_type": path_type, "workdir": workdir}


def filter_columns(columns: list) -> dict:
    filter_how = Prompt.ask(
        "Would you like to whitelist or blacklist some columns?",
        choices=["whitelist", "blacklist", "neither"],
        default="neither",
    )
    if filter_how == "neither":
        return {}
    explain_multiple_choice()
    filter_what = []
    while True:
        ans = Prompt.ask(
            f"Which column(s) would you like to {filter_how}?", choices=columns + [""]
        )
        if ans:
            filter_what.append(ans)
        else:
            break
    if len(filter_what) == 0:
        return {}
    return {filter_how: filter_what}


# endregion

# region Chains


# These are the functions that would be called from the command line :)
# (and use click)
@click.group()
def mdtab():
    pass


@mdtab.command()
@click.option("--sep", default=",")
@click.option("--irods/--no-irods", default=False)
@click.argument("example")
@click.argument("output", type=click.File("w"))
def setup(example, output, sep=",", irods=True):
    """Parse the contents of the example file and generate a config yaml file for preprocessing."""
    import re
    import yaml

    # only connect to irods if requested
    if irods:
        try:
            env_file = os.environ["IRODS_ENVIRONMENT_FILE"]
        except KeyError:
            env_file = os.path.expanduser("~/.irods/irods_environment.json")

        ssl_settings = {}
        with iRODSSession(irods_env_file=env_file, **ssl_settings) as session:
            sheets = parse_tabular_file(example, session, sep)
    else:
        sheets = parse_tabular_file(example, separator=sep)

    # select which sheets to use, if there are more than one
    selection_of_sheets = select_sheets(sheets)
    sheets = {k: v for k, v in sheets.items() if k in selection_of_sheets}

    # identify the column with data objects identifiers
    dataobject_column = identify_dataobject_column(sheets)
    # only keep sheets that contain that column
    sheets = {k: v for k, v in sheets.items() if dataobject_column in v.columns}

    # start config yaml with the info we have
    for_yaml = {
        "sheets": list(sheets.keys()),
        "separator": sep,
        "path_column": {
            "column_name": dataobject_column,
        },
    }

    # check the first data object name to see if it is absolute
    first_dataobject = list(sheets.values())[0][dataobject_column][0]
    if re.match("/[a-z_]+/home/[^/]+/", first_dataobject):
        dataobject_column_type = {"path_type": "absolute"}
    else:
        # if the path is not absolute, ask:
        # - whether it is relative or part of a filename
        # - in which working directory (at least project level) it should be searched
        dataobject_column_type = classify_dataobject_column(dataobject_column)
    # add path and working directory info to the yaml
    for_yaml["path_column"].update(dataobject_column_type)

    # ask if any columns need to be blacklisted OR whitelisted
    column_filter = filter_columns(
        list(
            set(
                [
                    col
                    for sheet in sheets.values()
                    for col in sheet.columns
                    if col != dataobject_column
                ]
            )
        )
    )
    # update yaml with column information
    for_yaml.update(column_filter)

    # create yaml from the dictionary
    yml = yaml.dump(for_yaml, default_flow_style=False, indent=2)
    # Make a group and indicate where it is saved
    console.print(Markdown("# This is your config yaml"))
    console.print(yml)
    click.echo(yml, file=output)


def do_something():
    return


# endregion

if __name__ == "__main__":
    mdtab()
