import dataclasses
import webbrowser
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict

import typer
from dumbo_utils.console import console
from dumbo_utils.url import compress_object_for_url
from dumbo_utils.validation import validate
from rich.table import Table

from valphi.controllers import Controller
from valphi.networks import NetworkTopology, ArgumentationGraph, MaxSAT, NetworkInterface


@dataclasses.dataclass(frozen=True)
class AppOptions:
    controller: Optional[Controller] = dataclasses.field(default=None)
    debug: bool = dataclasses.field(default=False)


class ShowSolutionOption(str, Enum):
    IF_WITNESS = "if-witness"
    ALWAYS = "always"
    NEVER = "never"


app_options = AppOptions()
app = typer.Typer()


def is_debug_on():
    return app_options.debug


def run_app():
    try:
        app()
    except Exception as e:
        if is_debug_on():
            raise e
        else:
            console.print(f"[red bold]Error:[/red bold] {e}")


@app.callback()
def main(
        val_phi_filename: Optional[Path] = typer.Option(
            None,
            "--val-phi",
            "-v",
            help=f"File containing the ValPhi function (default to {Controller.default_val_phi()})",
        ),
        network_filename: Path = typer.Option(
            ...,
            "--network-topology",
            "-t",
            help="File containing the network topology",
        ),
        filenames: List[Path] = typer.Option(
            [],
            "--filename",
            "-f",
            help="One or more files to parse",
        ),
        weight_constraints: bool = typer.Option(False, help="Use weight constraints instead of ad-hoc propagator"),
        ordered: bool = typer.Option(False, help="Add ordered encoding for eval/3"),
        debug: bool = typer.Option(False, "--debug", help="Show stacktrace and debug info"),
):
    """
    Neural Network evaluation under fuzzy semantics.

    Use --help after a command for the list of arguments and options of that command.
    """
    global app_options

    validate('network_filename', network_filename.exists() and network_filename.is_file(), equals=True,
             help_msg=f"File {network_filename} does not exists")
    for filename in filenames:
        validate('filenames', filename.exists() and filename.is_file(), equals=True,
                 help_msg=f"File {filename} does not exists")

    val_phi = Controller.default_val_phi()
    if val_phi_filename is not None:
        validate('val_phi_filename', val_phi_filename.exists() and val_phi_filename.is_file(), equals=True,
                 help_msg=f"File {val_phi_filename} does not exists")
        with open(val_phi_filename) as f:
            val_phi = [float(x) for x in f.readlines() if x]

    lines = []
    for filename in filenames:
        with open(filename) as f:
            lines += f.readlines()

    with open(network_filename) as f:
        network_filename_lines = f.readlines()
        network = NetworkInterface.parse(network_filename_lines)

    if type(network) is MaxSAT:
        validate("val_phi cannot be changed for MaxSAT", val_phi_filename is None, equals=True)
        val_phi = network.val_phi

    controller = Controller(
        network=network,
        val_phi=val_phi,
        raw_code='\n'.join(lines),
        use_wc=weight_constraints,
        use_ordered_encoding=ordered,
    )

    app_options = AppOptions(
        controller=controller,
        debug=debug,
    )


def network_values_to_table(values: Dict, *, title: str = "") -> Table:
    network = app_options.controller.network
    table = Table(title=title)
    if type(network) is NetworkTopology:
        table.add_column("Node")
        max_nodes = 0
        for layer_index, _ in enumerate(range(network.number_of_layers()), start=1):
            table.add_column(f"Layer {layer_index}")
            nodes = network.number_of_nodes(layer=layer_index)
            max_nodes = max(nodes, max_nodes)

        for node_index, _ in enumerate(range(max_nodes), start=1):
            table.add_row(
                str(node_index),
                *(str(values[(layer_index, node_index)] / app_options.controller.max_value)
                  if node_index <= network.number_of_nodes(layer_index) else None
                  for layer_index, _ in enumerate(range(network.number_of_layers()), start=1))
            )
    elif type(network) is ArgumentationGraph:
        table.add_column("Node")
        table.add_column("Truth degree")
        for node, _ in enumerate(network.arguments, start=1):
            table.add_row(
                str(node),
                str(values[f"{network.term(node)}"]),
            )
    elif type(network) is MaxSAT:
        table.add_column("# of satisfied clauses / Atom / Clause")
        table.add_column("Value")
        for node in values.keys():
            if node.startswith("even"):
                continue
            value = values[node]
            if node != "sat":
                value = "false" if value == 0 else "true"
            table.add_row(
                str(node),
                str(value),
            )
    return table


@app.command(name="solve")
def command_solve(
        number_of_solutions: int = typer.Option(
            0,
            "--number-of-solutions",
            "-s",
            help="Maximum number of solutions to compute (0 for unbounded)",
        ),
        show_in_asp_chef: bool = typer.Option(
            default=False,
            help="Open solutions with ASP Chef",
        ),
) -> None:
    """
    Run the program and print solutions.
    """
    validate('number_of_solutions', number_of_solutions, min_value=0)

    with console.status("Running..."):
        res = app_options.controller.find_solutions(number_of_solutions)
    if not res:
        console.print('NO SOLUTIONS')
    for index, values in enumerate(res, start=1):
        console.print(network_values_to_table(values, title=f"Solution {index}"))
    if show_in_asp_chef:
        for index, values in enumerate(res, start=1):
            url = "https://asp-chef.alviano.net/open#"
            # url = "http://localhost:5188/open#"
            graph = app_options.controller.network.network_facts.filter(when=lambda atom: atom.predicate_name == "attack").as_facts
            evaluation = '\n'.join(f"eval({node},{','.join(value.split('/'))})." for node, value in values.items())
            url += compress_object_for_url({"input": graph + '\n' + evaluation}, suffix="")
            url += ";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%21"
            webbrowser.open(url, new=0, autoraise=True)


@app.command(name="query")
def command_query(
        query: Optional[str] = typer.Argument(
            None,
            help=f"A string representing the query as an alternative to --query-filename",
        ),
        query_filename: Optional[Path] = typer.Option(
            None,
            "--query-filename",
            "-q",
            help=f"File containing the query (as an alternative to providing the query from the command line)",
        ),
        show_solution: ShowSolutionOption = typer.Option(
            ShowSolutionOption.IF_WITNESS,
            "--show-solution",
            "-s",
            case_sensitive=False,
            help="Enforce or inhibit the printing of the computed solution",
        ),
) -> None:
    """
    Answer the provided query.
    """
    validate("query", query is None and query_filename is None, equals=False, help_msg="No query was given")
    validate("query", query is not None and query_filename is not None, equals=False,
             help_msg="Option --query-filename cannot be used if the query is given from the command line")

    if query_filename is not None:
        validate("query_filename", query_filename.exists() and query_filename.is_file(), equals=True,
                 help_msg=f"File {query_filename} does not exists")
        with open(query_filename) as f:
            query = ''.join(x.strip() for x in f.readlines())

    with console.status("Running..."):
        res = app_options.controller.answer_query(query=query)
    title = f"{str(res.true).upper()}: typical individuals of the left concept are assigned {res.left_concept_value}" \
        if res.consistent_knowledge_base else f"TRUE: the knowledge base is inconsistent!"
    console.print(title)
    if show_solution == ShowSolutionOption.ALWAYS or (show_solution == ShowSolutionOption.IF_WITNESS and res.witness):
        console.print(network_values_to_table(res.assignment))

