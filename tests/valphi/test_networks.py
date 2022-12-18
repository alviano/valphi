import pytest

from valphi import utils
from valphi.networks import NetworkTopology, MaxSAT, NetworkInterface


def two_layers_three_nodes_network(with_exactly_one: bool = False):
    res = NetworkTopology() \
        .add_layer() \
        .add_node() \
        .add_node() \
        .add_layer() \
        .add_node([10, 20, -10])
    if with_exactly_one:
        res.add_exactly_one([1, 2])
    return res.complete()


def test_network_topology_must_start_with_add_node():
    with pytest.raises(utils.ValidationError):
        NetworkTopology().add_node()

    network = NetworkTopology().add_layer().add_node().complete()
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
    network = NetworkInterface.parse(text)
    assert network == two_layers_three_nodes_network()


def test_parse_network_with_exactly_one():
    text = """
10 20 -10
=1 1 2
    """
    network = NetworkInterface.parse(text)
    assert network == two_layers_three_nodes_network(with_exactly_one=True)


def test_network_topology_as_facts():
    facts = two_layers_three_nodes_network(with_exactly_one=True).network_facts.as_strings()
    assert 'sub_type(l2_1,bias(l1),"10").' in facts
    assert 'sub_type(l2_1,l1_1,"20").' in facts
    assert 'sub_type(l2_1,l1_2,"-10").' in facts
    assert 'exactly_one(0).' in facts
    assert 'exactly_one(0,l1_1).' in facts
    assert 'exactly_one(0,l1_1).' in facts


def test_max_sat_one_clause():
    max_sat = MaxSAT()
    max_sat.add_clause(1, 2, -3)
    max_sat.complete()
    assert max_sat.serialize_clauses_as_facts() == [
        "clause(c(1)).",
        "clause_positive_literal(c(1), x1).",
        "clause_positive_literal(c(1), x2).",
        "clause_negative_literal(c(1), x3).",
    ]
    assert {str(atom) for atom in max_sat.network_facts} == {
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
    max_sat = NetworkInterface.parse("""
p cnf 0 0
1 2 0
-1 0
-2 0
    """.strip())
    assert max_sat.number_of_clauses == 3
    assert max_sat.val_phi == [0, 3, 6]
