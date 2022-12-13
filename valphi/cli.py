import dataclasses
from pathlib import Path
from typing import List, Optional, Dict

import typer
from rich.table import Table

from valphi import utils
from valphi.controllers import Controller
from valphi.networks import NetworkTopology, ArgumentationGraph
from valphi.utils import console


@dataclasses.dataclass(frozen=True)
class AppOptions:
    controller: Optional[Controller] = dataclasses.field(default=None)
    debug: bool = dataclasses.field(default=False)


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
        number_of_solutions: int = typer.Option(
            0,
            "--number-of-solutions",
            "-s",
            help="Maximum number of solutions to compute (0 for unbounded)",
        ),
        # max_value: int = typer.Option(
        #     5,
        #     "--max-value",
        #     "-n",
        #     help="Maximum value for truth degrees (use rational values 0/n ... n/n)",
        # ),
        wc: bool = typer.Option(False, help="Use weight constraints instead of ad-hoc propagator"),
        ordered: bool = typer.Option(False, help="Add ordered encoding for eval/2"),
        debug: bool = typer.Option(False, "--debug", help="Don't minimize browser"),
):
    """
    Neural Network evaluation under fuzzy semantics.

    Use --help after a command for the list of arguments and options of that command.
    """
    global app_options

    utils.validate('number_of_solutions', number_of_solutions, min_value=0)
    # utils.validate('max_value', max_value, min_value=0)
    utils.validate('network_filename', network_filename.exists() and network_filename.is_file(), equals=True,
                   help_msg=f"File {network_filename} does not exists")
    for filename in filenames:
        utils.validate('filenames', filename.exists() and filename.is_file(), equals=True,
                       help_msg=f"File {filename} does not exists")

    if val_phi_filename is not None:
        utils.validate('val_phi_filename', val_phi_filename.exists() and val_phi_filename.is_file(), equals=True,
                       help_msg=f"File {val_phi_filename} does not exists")
        with open(val_phi_filename) as f:
            val_phi = [float(x) for x in f.readlines() if x]

    lines = []
    for filename in filenames:
        with open(filename) as f:
            lines += f.readlines()

    with open(network_filename) as f:
        network_filename_lines = f.readlines()
        network = ArgumentationGraph.parse(network_filename_lines)
        if network is None:
            network = NetworkTopology.parse(network_filename_lines)

    controller = Controller(
        network=network,
        val_phi=val_phi if val_phi_filename is not None else Controller.default_val_phi(),
        raw_code='\n'.join(lines),
        max_stable_models=number_of_solutions,
        use_wc=wc,
        use_ordered_encoding=ordered,
    )

    app_options = AppOptions(
        controller=controller,
        debug=debug,
    )


def network_values_to_table(values: Dict, *, title: str = "") -> Table:
    network = app_options.controller.network
    table = Table(title=title)
    table.add_column("Node" if type(app_options.controller.network) is ArgumentationGraph else "Layer")
    max_nodes = 0
    for layer_index, _ in enumerate(range(network.number_of_layers()), start=1):
        nodes = network.number_of_nodes(layer=layer_index)
        max_nodes = max(nodes, max_nodes)
    for node_index, _ in enumerate(range(max_nodes), start=1):
        table.add_column("Value" if type(app_options.controller.network) is ArgumentationGraph else f"Node {node_index}")

    for layer_index, _ in enumerate(range(network.number_of_layers()), start=1):
        nodes = network.number_of_nodes(layer=layer_index)
        table.add_row(
            str(layer_index),
            *(str(values[(layer_index, node_index)] / app_options.controller.max_value)
              for node_index, _ in enumerate(range(nodes), start=1))
        )
    return table


@app.command(name="solve")
def command_solve() -> None:
    """
    Run the program and print solutions.
    """
    with console.status("Running..."):
        res = app_options.controller.find_solutions()
    if not res:
        console.print('NO SOLUTIONS')
    for index, values in enumerate(res, start=1):
        console.print(network_values_to_table(values, title=f"Solution {index}"))


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
) -> None:
    """
    Answer the provided query.
    """
    utils.validate("query", query is None and query_filename is None, equals=False,
                   help_msg="No query was given")
    utils.validate("query", query is not None and query_filename is not None, equals=False,
                   help_msg="Option --query-filename cannot be used if the query is given from the command line")

    if query_filename is not None:
        utils.validate("query_filename", query_filename.exists() and query_filename.is_file(), equals=True,
                       help_msg=f"File {query_filename} does not exists")
        with open(query_filename) as f:
            query = ''.join(x.strip() for x in f.readlines())

    with console.status("Running..."):
        res = app_options.controller.answer_query(query=query)
    if res.query_true is None:
        console.print("UNKNOWN")
    else:
        title = f"{str(res.query_true).upper()}: left concept {res.left_concept_value}; " \
                f"right concept {res.right_concept_value} {'>=' if res.query_true else '<'} {res.threshold}"
        if res.query_true:
            title += f" (the implication reaches the threshold in all solutions where the left concept is " \
                     f"{res.left_concept_value})"
        console.print(network_values_to_table(res.eval_values, title=title))
