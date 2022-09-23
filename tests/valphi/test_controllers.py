from valphi.controllers import Controller
from valphi.networks import NetworkTopology


def two_layers_three_nodes_network():
    return NetworkTopology()\
        .add_layer()\
        .add_node()\
        .add_node()\
        .add_exactly_one([1, 2])\
        .add_layer()\
        .add_node([10, 20, -10])


def test_network_topology_as_facts():
    network = two_layers_three_nodes_network()
    facts = Controller.network_topology_as_facts(network)
    assert 'sub_type(l2_1,bias(l1),"10").' in facts
    assert 'sub_type(l2_1,l1_1,"20").' in facts
    assert 'sub_type(l2_1,l1_2,"-10").' in facts
    assert 'exactly_one(0).' in facts
    assert 'exactly_one(0,l1_1).' in facts
    assert 'exactly_one(0,l1_1).' in facts


def test_network_topology_output():
    network = two_layers_three_nodes_network()
    controller = Controller(network=network)
    models = controller.find_solutions()
    assert len(models) == 2
    for model in models:
        assert model[(1, 1)] + model[(1, 2)] == controller.max_value
