import click
import yaml
from rich.prompt import Prompt, Confirm
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from pathlib import Path

excel_contents = [
    {"sheet": "sheet1", "columns": ["fileid", "md1", "md2"]},
    {"sheet": "sheet2", "columns": ["fileid", "md3", "md4"]},
    {"sheet": "sheet3", "columns": ["md5", "md6"]},
]

console = Console()


@click.group()
def cli():
    pass


@cli.command()
def setup():
    console.print(Markdown("## Let's look at this imaginary Excel!"))
    sheets = [x["sheet"] for x in excel_contents]
    sheet = Prompt.ask(
        "Which sheet would you like to select, Rich?",
        default="all",
        choices=["all"] + sheets,
    )
    panel1 = Panel(sheet, title="Which sheets")
    console.print(panel1)
    if sheet == "all":
        columns = set([col for sheet in excel_contents for col in sheet["columns"]])
        click.echo(
            f"You have chosen to use all sheets, covering the following columns: {columns}"
        )
    else:
        columns = excel_contents[sheets.index(sheet)]["columns"]
        click.echo(
            f"You have chosen to use '{sheet}', with the following columns: {columns}."
        )

    path_column = Prompt.ask(
        "Which column contains an unique identifier of the target data object?",
        choices=columns,
    )
    path_type = Prompt.ask(
        f"How is the path coded in the column '{path_column}'? If the column contains a unique identifier that is only part of the filename, choose 'part'.",
        choices=["absolute", "relative", "part"],
    )

    for_yaml = {
        "sheet": [sheet] if sheet != all else columns,
        "path_column": {"column_name": path_column, "path_type": path_type},
    }
    if path_type != "absolute":

        def validate_absolute_irods_path(prompt_input: str):
            if not prompt_input.startswith("/"):
                prompt_input = "/" + prompt_input
            prompt_input = Path(prompt_input)
            if len(prompt_input.parts) < 4 or prompt_input.parts[2] != "home":
                raise click.UsageError(
                    "Please provide a path starting with the pattern /{zone}/home/{project}"
                )
            return str(prompt_input)

        workdir = click.prompt(
            "What is the absolute path of the directory where we can find the files? (It should start with /{zone}/home/{project})",
            value_proc=validate_absolute_irods_path,
        )
        for_yaml["working_dir_prefix"] = workdir
        if path_type == "relative":
            click.echo(
                f"Excellent, now the relative paths in the '{path_column}' column will be chained to the collection path '{workdir}'!"
            )
        else:
            click.echo(
                f"Excellent, data objects are going to be found by querying the contents of '{path_column}' within '{workdir}'!"
            )
    else:
        click.echo(
            f"Excellent, we'll expect the contents of the '{path_column}' column to be absolute paths!"
        )  # we could validate this before providing the option
    if sheet == "all":
        for s in excel_contents:
            if path_column not in s["columns"]:
                click.echo(
                    f"The '{path_column}' is missing from the '{s['sheet']}' sheet so this sheet will be excluded."
                )
                sheets.pop(sheets.index(s["sheet"]))
        columns = set(
            [
                col
                for sheet in excel_contents
                for col in sheet["columns"]
                if sheet["sheet"] in sheets
            ]
        )

    exclude_columns = Confirm.ask("Would you like to exclude any of the columns?")
    if exclude_columns:
        excludable_columns = [col for col in columns if col != path_column]

        def check_columns_to_exclude(prompt_input: str):
            columns_to_exclude = prompt_input.split()
            if not all(x in excludable_columns for x in columns_to_exclude):
                raise click.UsageError("Not all these columns exist!")
            return columns_to_exclude

        columns_to_exclude = click.prompt(
            f"Please list the columns to exclude separating them by spaces ({', '. join(excludable_columns)})",
            value_proc=check_columns_to_exclude,
        )
        click.echo(columns_to_exclude)

        def get_excluded_column_in_sheet(excelsheet):
            if sheet != "all" and excelsheet["sheet"] != sheet:
                return False
            if excelsheet["sheet"] not in sheets:
                return False
            cols = [col for col in columns_to_exclude if col in excelsheet["columns"]]
            if len(cols) == 0:
                return False
            return {"sheet": excelsheet["sheet"], "columns": cols}

        exclude_columns_info = [
            get_excluded_column_in_sheet(excelsheet) for excelsheet in excel_contents
        ]
        for_yaml["exclude_columns"] = [
            colinfo for colinfo in exclude_columns_info if colinfo
        ]
    yml = yaml.dump(for_yaml, default_flow_style=False, indent=2)
    print(yml)
    output_yaml = click.prompt(
        "Where do you want to store your configuration?",
        default="-",
        type=click.File("w"),
    )
    click.echo(yml, file=output_yaml)


if __name__ == "__main__":
    cli()
