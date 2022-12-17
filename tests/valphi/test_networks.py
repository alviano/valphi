import pytest

from valphi import utils
from valphi.networks import NetworkTopology, MaxSAT


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


def test_max_sat_one_clause():
    max_sat = MaxSAT()
    max_sat.add_clause(1, 2, -3)
    assert max_sat.serialize_clauses_as_facts() == [
        "clause(c(1)).",
        "clause_positive_literal(c(1), x1).",
        "clause_positive_literal(c(1), x2).",
        "clause_negative_literal(c(1), x3).",
    ]
    assert {str(atom) for atom in max_sat.compute_network_facts()} == {
        'sub_type(x1,x1,2)',
        'sub_type(x2,x2,2)',
        'sub_type(x3,x3,2)',
        'sub_type(c(1),x1,1)',
        'sub_type(c(1),x2,1)',
        'sub_type(c(1),x3,-1)',
        'sub_type(c(1),bias(c(1)),1)',
        "sub_type(sat,c(1),1)",
        'sub_type(even(0),bias(even(0)),1)',
        "sub_type(even(1),even'(1),1)",
        "sub_type(even(1),even''(1),1)",
        "sub_type(even'(1),c(1),1)",
        "sub_type(even'(1),even(0),-1)",
        "sub_type(even''(1),c(1),-1)",
        "sub_type(even''(1),even(0),1)",
    }


def test_max_sat_parse():
    max_sat = MaxSAT.parse("""
p cnf 0 0
1 2 0
-1 0
-2 0
    """.strip())
    assert len(max_sat) == 3
    assert max_sat.compute_val_phi() == [0, 3, 6]
