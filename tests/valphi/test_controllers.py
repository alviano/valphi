import pytest

from valphi.controllers import Controller
from valphi.networks import NetworkTopology, ArgumentationGraph


@pytest.fixture
def two_layers_three_nodes_network():
    return NetworkTopology()\
        .add_layer()\
        .add_node()\
        .add_node()\
        .add_exactly_one([1, 2])\
        .add_layer()\
        .add_node([10, 20, -10])


def test_network_topology_as_facts(two_layers_three_nodes_network):
    facts = Controller.network_topology_as_facts(two_layers_three_nodes_network)
    assert 'sub_type(l2_1,bias(l1),"10").' in facts
    assert 'sub_type(l2_1,l1_1,"20").' in facts
    assert 'sub_type(l2_1,l1_2,"-10").' in facts
    assert 'exactly_one(0).' in facts
    assert 'exactly_one(0,l1_1).' in facts
    assert 'exactly_one(0,l1_1).' in facts


def test_network_topology_output(two_layers_three_nodes_network):
    controller = Controller(network=two_layers_three_nodes_network)
    models = controller.find_solutions()
    assert len(models) == 2
    for model in models:
        assert model[(1, 1)] + model[(1, 2)] == controller.max_value


def test_use_wc(two_layers_three_nodes_network):
    controller = Controller(network=two_layers_three_nodes_network, use_wc=True)
    models = controller.find_solutions()
    assert len(models) == 2
    for model in models:
        assert model[(1, 1)] + model[(1, 2)] == controller.max_value


def check_all_options(network):
    simple = Controller(network=network, use_wc=False, use_ordered_encoding=False).find_solutions()
    wc = Controller(network=network, use_wc=True, use_ordered_encoding=False).find_solutions()
    ordered = Controller(network=network, use_wc=False, use_ordered_encoding=True).find_solutions()
    wc_ordered = Controller(network=network, use_wc=True, use_ordered_encoding=True).find_solutions()
    assert set(str(x) for x in simple) == set(str(x) for x in wc)
    assert set(str(x) for x in simple) == set(str(x) for x in ordered)
    assert set(str(x) for x in simple) == set(str(x) for x in wc_ordered)


def check_all_options_for_query(network, query):
    simple = Controller(network=network, use_wc=False, use_ordered_encoding=False).answer_query(query)
    wc = Controller(network=network, use_wc=True, use_ordered_encoding=False).answer_query(query)
    ordered = Controller(network=network, use_wc=False, use_ordered_encoding=True).answer_query(query)
    wc_ordered = Controller(network=network, use_wc=True, use_ordered_encoding=True).answer_query(query)
    assert simple.query_true == wc.query_true
    assert simple.query_true == ordered.query_true
    assert simple.query_true == wc_ordered.query_true


def test_small_graph():
    graph = ArgumentationGraph.parse("""
#graph
1 2 3
2 3 -5
2 4 4
3 4 -4
4 5 -5000
5 4 -5000
    """)
    check_all_options(graph)


def test_kbmonk1():
    graph = NetworkTopology.parse("""
487 -6503 1211 5356 -6692 6458 225 97 -12 -77 -17 -87 5735 -2257 -2232 -1711 -110 -112
142 618 1940 -3597 2130 864 -2428 131 135 460 152 197 4337 -1410 -1110 -1452 434 132
525 -1660 2973 -1267 -2032 4261 -1840 53 107 -8 149 24 -865 495 383 480 276 311
#
-3671 9249 8640 -9420
=1 1 2 3
=1 4 5 6
=1 7 8
=1 9 10 11
=1 12 13 14 15
=1 16 17
    """)
    check_all_options(graph)


def test_small_kbmonk1_query():
    graph = NetworkTopology.parse("""
487 -6503 1211 5356 -6692 6458 225 97 -12 -77 -17 -87 5735 -2257 -2232 -1711 -110 -112
142 618 1940 -3597 2130 864 -2428 131 135 460 152 197 4337 -1410 -1110 -1452 434 132
525 -1660 2973 -1267 -2032 4261 -1840 53 107 -8 149 24 -865 495 383 480 276 311
#
-3671 9249 8640 -9420
=1 1 2 3
=1 4 5 6
=1 7 8
=1 9 10 11
=1 12 13 14 15
=1 16 17
    """)
    query = ''.join([line.strip() for line in """
l3_1
#
or(
    l1_12,
    or(
        and(l1_1,l1_4),
        or(
            and(l1_2,l1_5),
            and(l1_3,l1_6)
        )
    )
)
#
1.0    
    """.strip().split('\n')])
    check_all_options_for_query(graph, query)
