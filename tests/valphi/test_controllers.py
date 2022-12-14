import pytest

from valphi import utils
from valphi.controllers import Controller
from valphi.networks import NetworkTopology, ArgumentationGraph


def parse_query(string):
    return ''.join([line.strip() for line in string.strip().split('\n')])


def read_example_file(filename):
    assert ".." not in filename
    with open(utils.PROJECT_ROOT / f"examples/{filename}") as f:
        return f.readlines()


def read_query_from_file(filename):
    return ''.join(x.strip() for x in read_example_file(f"{filename}.query"))


def read_network_from_file(filename):
    return NetworkTopology.parse('\n'.join(read_example_file(f"{filename}.network")))


def read_graph_from_file(filename):
    return ArgumentationGraph.parse('\n'.join(read_example_file(f"{filename}.graph")))


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


@pytest.fixture
def kbmonk1():
    return read_network_from_file("kbmonk1")


def kbmonk1_queries():
    return [
        read_query_from_file(f"kbmonk1-{index + 1}") for index in range(7)
    ]


def test_kbmonk1_solve(kbmonk1):
    check_all_options(kbmonk1)


@pytest.mark.parametrize("query", kbmonk1_queries())
def test_kbmonk1_query(kbmonk1, query):
    check_all_options_for_query(kbmonk1, query)


def graphs():
    return [
        read_graph_from_file(f"small-{index + 1}") for index in range(6)
    ]


@pytest.mark.parametrize("graph", graphs())
def test_solve_graph(graph):
    check_all_options(graph)


def small_graph_5_queries():
    return [
        read_query_from_file(f"small-5-{index + 1}") for index in range(5)
    ]


def small_graph_6_queries():
    return [
        read_query_from_file(f"small-6-{index + 1}") for index in range(11)
    ]


@pytest.mark.parametrize("query", small_graph_5_queries())
def test_solve_small_graph_5_with_query(query):
    graph = read_graph_from_file("small-5")
    check_all_options_for_query(graph, query)


@pytest.mark.parametrize("query", small_graph_6_queries())
def test_solve_small_graph_6_with_query(query):
    graph = read_graph_from_file("small-6")
    check_all_options_for_query(graph, query)
