import pytest

from valphi import utils
from valphi.networks import NetworkTopology


def two_layers_three_nodes_network():
    return NetworkTopology() \
        .add_layer() \
        .add_node() \
        .add_node() \
        .add_layer() \
        .add_node([10, 20, -10])


def test_network_topology_must_start_with_add_node():
    with pytest.raises(utils.ValidationError):
        NetworkTopology().add_node()

    network = NetworkTopology().add_layer().add_node()
    assert network.number_of_layers() == 1
    assert network.number_of_nodes(layer=1) == 1


def test_two_layers_three_nodes_network():
    network = two_layers_three_nodes_network()
    assert network.number_of_layers() == 2
    assert network.number_of_nodes(layer=1) == 2
    assert network.number_of_nodes(layer=2) == 1
    assert network.in_weights(layer=2, node=1) == [10, 20, -10]


def test_parse_network():
    text = """
10 20 -10
    """
    network = NetworkTopology.parse(text)
    assert network == two_layers_three_nodes_network()


def test_parse_network_with_exactly_one():
    text = """
10 20 -10
=1 1 2
    """
    network = NetworkTopology.parse(text)
    assert network == two_layers_three_nodes_network().add_exactly_one([1, 2])
