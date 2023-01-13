import pytest
from click import UsageError
from typer.testing import CliRunner

from valphi.cli import app


@pytest.fixture
def runner():
    return CliRunner()


def test_network_topology_is_required(runner):
    result = runner.invoke(app)
    assert result.exit_code == UsageError.exit_code
    assert "Error" in result.stdout
    assert "Missing option '--network-topology' / '-t'." in result.stdout
