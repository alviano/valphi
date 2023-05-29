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
        url = "https://asp-chef.alviano.net/open#"
        # url = "http://localhost:5188/open#"
        graph = app_options.controller.network.network_facts.filter(when=lambda atom: atom.predicate_name == "attack").as_facts
        models = []
        for values in res:
            models.append(graph)
            models.append('\n'.join(f"eval({node},{','.join(value.split('/'))})." for node, value in values.items()))
            models.append('§')
        url += compress_object_for_url({"input": '\n'.join(models[:-1])}, suffix="")
        url += ";eJzNV8uWqsgS/SVAPKcZ9EBEIBHS5iGQORMoITERb6PF4+tvJGq1dbpuD7pPr3UHLFflIzIeO/aOehudS3bW5WKNviUjYmnYM5os60wJeKrwW27HEqovDUmGiYo9K37saXJh3+8VtiOLvbyJ60OqczifvYFdCnuo3qjUWEm08UY38pdeTa7YMDlhkoqbjewm3oAtopCpVElt1l6IOtRoPU2dqrD4e8bAxmmQyWN9Xjt7bHfuWL4I3nN4gzZmlyt72Df73BqW8L6Un2Purp3pYGmLV/8PVnyhSgUxtaNnrOAOBnsBz84+2zGnKSD2+7v6JZe1G00K4YdCw2raxsMNrfULZfoEMV+yJr/li5htbQ9+g/GQLM/uejWIbxuutN9CPUdMhk+X4N1baqklWq9KyJNUpM4NGWaesVVJhW+z7VWJbIcXdjzCej+fh3vUHMCP5Sm1lnnWUDlrsHRItBuyMcQivx8Sv31b92XG+GwvZysN2QHEFV9JE49bu/zw7xHDSNNAzhu1LCztGUvrhb/Ad72SNGjdJlbzdXnN2eki7vz1+8EN3uiQpV5mn21UQuxSpizlLHF4zirVPWMpb/iNji8+Gpv3rbH5PUtM6bBe8jd71bopuvzo42O/ySztHWyNaN1CrMtbkciMpqjcjqverffw9pJnjc+g7vCL3wGrxxzySS1eQ0yAy5alssZIijmug2M6OtoxHL6jhp/EHjaqZpfgilr+FUf55DFJokbRuInTkMa7kmkzeImv4pqfdlEO3dKzbKHzvDHv+QAbeyWu8ga3aCOL9zs49e/g9uzImRVP4k06VjfRk9vN5uKu9Y5AzrN1pW/DHuobq4WpQc8OIneLg8UlGp6gVhT88dt0jdTcLiHH2i1b4J4kmMPaxTXnGjzvjVRBrVfv5S2rdm5MLq6kdt66H3G0/0/MtN02PF2Q0V4BrwpJ+tYPh8TdqBeXD4B7wJ01AMY6sb4WfmWWCTzTt/H4vGdKhWXWh7HS3Q3qYP3Le0TRumyB2rwp2NZAMg7bNmJysg21nQt5mX3k5D0SuA1X39xQrwo7qIhyt+GauchRggyp9F/xa+Yd3Ome/qfjcJz9Z6J+Txyjb97Mc+YlV0TuP+p151BTq4AzIGdL0VMV9JsE9X+pc8DB/xONtR444HQArBXWXvDOMVWcCs4o2NSOAlc0wW0ma08cn1LlhacaWmU25sdU6v7gWV+lyWbCClHcaNUTwbMWxB1KS2/i3I0o2xkO8yKiUvgw+4JnOeaAqbpY61jgKVv/I+w+/77OtkwN6hjwN7jrQRO6dseAt2bO9Qxc07o4Qb8tRW+5UVB7FrruDAK6Ii08K+Y02Su0RpM3IdHf77kVj9DTl0xRhQ0batIffo6/LU34+WCDbzXpAeMsa+aajSQJLkUKdmvUw7kfa3j+qNv4oolPPoA+FfvPv+d6Wtoo1t+SuMuED6/7C8iVHRwfeBf2Rwr5+lzzfb8zSokoMeRspXoR8Ja1H7xRUknkL9yoVHeJWVFjsyQRfONf1tz/Ix7A9p3bZl4TGIY3J9CK/pWTSKr3mX2CPAdjkUBuzxD7Iv/A5+cczf2SoWbuL5Z+wgDU1YA5oS4XeC0peMIVYKABrr0CjhWIR/DMRCOd7xKvx9P+KwxE2cKRkOUskQnaAbUiiglcpwN/6TrwBfRwfCv+GUY+Ys8VbSxeMX2fjSaoxQ30BnTuaS/+rDFTcCL1CmJZXYniA74kidS8dhM0UGt/Bf054Uiv8LSBechhX2lMCFpM0/KeA1vEvxS5/Q75l7LF6jX/VW7r3Vv4isfqvXjlpPNrrgQetONhtl/9SR9pfRqxwWuv3lxpE5ygLqCPvgT6yHBUQjzQpxZZQi/X2NhP/y/6CFCrYcbqUvmXNgz7wQWdnDXHfI21ctwftGsbwrwD+YC4OuCv43Zz6jw2JA9dOYr5GGJQ73YHXoC/oMFdzAahh0K/4Izor+Fu3/CExpQ7JpXg0x07D7s0hZqBZrsmEWdm3Zzz95jhIA6YKx3gID5RwUHPnmvuM3qqmNNdI8ScZYIeBdOXc/viz/UmjQl4JBLEMc9OBDCSAo5nrUpmDrpB/4re+RLTgNulF20kCpztGUiF2f6BaedEGv/qCWxHFcxc+9GL4uorXASib2Ze2pe+jJOfxD9PXf5Cb591EfiD/1usGQt9kfqv9yHXeiX8fHDw3t+jvz1fUkOvPZgnqeFdaQ2zJOTJS/YL0fu7CHIXlSOJqgr6n5OJ/K/5sgONkT5xHODhp3OBwBjvfoynOKZycfR//fW/mNbq2Q==%21"
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

