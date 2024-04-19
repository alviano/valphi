import dataclasses
import webbrowser
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict

import typer
from dumbo_asp.queries import pack_asp_chef_url
from dumbo_utils.console import console
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
        url = "https://asp-chef.alviano.net/"
        # url = "http://localhost:5188/"
        url += "#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%21"
        graph = app_options.controller.network.as_attack_graph().as_facts
        models = []
        for values in res:
            models.append(f"max_value({app_options.controller.max_value}).")
            models.append(graph)
            models.append('\n'.join(
                f"eval({node if type(node) is str else 'l' + '_'.join(str(x) for x in node)},"
                f"anonymous,{value.split('/')[0]})."
                for node, value in values.items()
            ))
            models.append('§')
        url = pack_asp_chef_url(url, the_input='\n'.join(models[:-1]))
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

