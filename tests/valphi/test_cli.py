import clingo
import pytest
from click import UsageError
from typer.testing import CliRunner

from valphi.cli import app
from valphi.utils import PROJECT_ROOT


@pytest.fixture
def runner():
    return CliRunner()


def test_network_topology_is_required(runner):
    result = runner.invoke(app)
    assert result.exit_code == UsageError.exit_code
    assert "Error" in result.stdout
    assert "Missing option '--network-topology' / '-t'." in result.stdout


def test_solve_feedforward_network_topology(runner):
    result = runner.invoke(app, [
        "-t", PROJECT_ROOT / "examples/kbmonk1.network",
        "solve",
        "-s", "10",
    ])
    assert result.exit_code == 0
    assert "Solution 10" in result.stdout
