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
        weight_constraints: Optional[int] = typer.Option(
            None,
            help="Use weight constraints instead of ad-hoc propagator. "
                 "It also requires a multiplier to approximate real numbers."
        ),
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
                *(str(values[(layer_index, node_index)])
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
        url = "https://asp-chef.alviano.net/open#"
        # url = "http://localhost:5188/open#"
        graph = app_options.controller.network.as_attack_graph().as_facts
        models = []
        for values in res:
            models.append(graph)
            models.append('\n'.join(f"eval({node if type(node) is str else 'l' + '_'.join(str(x) for x in node)},{','.join(value.split('/'))})." for node, value in values.items()))
            models.append('§')
        url += compress_object_for_url({"input": '\n'.join(models[:-1])}, suffix="")
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

