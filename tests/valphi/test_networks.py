import pytest
from dumbo_asp.utils import ValidationError

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
    with pytest.raises(ValidationError):
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
    facts = two_layers_three_nodes_network(with_exactly_one=True).network_facts.as_facts
    assert 'weighted_typicality_inclusion(l2_1,top,"10").' in facts
    assert 'weighted_typicality_inclusion(l2_1,l1_1,"20").' in facts
    assert 'weighted_typicality_inclusion(l2_1,l1_2,"-10").' in facts
    assert 'exactly_one(0).' in facts
    assert 'exactly_one_element(0,l1_1).' in facts
    assert 'exactly_one_element(0,l1_1).' in facts


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
        'crisp(x1)',
        'crisp(x2)',
        'crisp(x3)',
        'crisp(c(1))',
        'crisp(even(0))',
        'crisp(even(1))',
        "crisp(even'(1))",
        "crisp(even''(1))",
        'weighted_typicality_inclusion(sat,c(1),1)',
        'weighted_typicality_inclusion(c(1),top,1)',
        'weighted_typicality_inclusion(c(1),x1,1)',
        'weighted_typicality_inclusion(c(1),x2,1)',
        'weighted_typicality_inclusion(c(1),x3,-1)',
        'weighted_typicality_inclusion(even(0),top,1)',
        "weighted_typicality_inclusion(even(1),even'(1),1)",
        "weighted_typicality_inclusion(even(1),even''(1),1)",
        "weighted_typicality_inclusion(even'(1),c(1),1)",
        "weighted_typicality_inclusion(even'(1),even(0),-1)",
        "weighted_typicality_inclusion(even''(1),c(1),-1)",
        "weighted_typicality_inclusion(even''(1),even(0),1)",
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
