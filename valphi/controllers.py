import dataclasses
from collections import namedtuple
from typing import List, Dict, Optional, Tuple

import clingo

from clingo.symbol import Number

from valphi import utils
from valphi.contexts import Context
from valphi.models import ModelCollect, ModelList, LastModel
from valphi.networks import NetworkTopology
from valphi.propagators import ValPhiPropagator

BASE_PROGRAM = """
% let's use max_value+1 truth degrees of the form 0/max_value ... max_value/max_value
val(0..max_value).


% classes from the network topology
class(C) :- sub_type(C,_,_).
class(C) :- sub_type(_,C,_).

% inputs have binary values (biases fixed to max_value)
{eval(C,0); eval(C,max_value)} = 1 :- class(C), not sub_type(C,_,_); C != bias(ID) : class(bias(ID)).
eval(bias(ID),max_value) :- class(bias(ID)), not sub_type(bias(ID),_,_).

% other classes take some value
{eval(C,V) : val(V)} = 1 :- class(C), sub_type(C,_,_).


% all relevant concept for the query
concept(C) :- query(C,D,_).
concept(D) :- query(C,D,_).
concept(A) :- concept(and(A,B)).
concept(B) :- concept(and(A,B)).
concept(A) :- concept(or(A,B)).
concept(B) :- concept(or(A,B)).
concept(A) :- concept(neg(A)).

% Godel evaluation of complex concepts
eval(and(A,B),@min(V1,V2))  :- concept(and(A,B)), eval(A,V1), eval(B,V2).
eval( or(A,B),@max(V1,V2))  :- concept( or(A,B)), eval(A,V1), eval(B,V2).
eval(neg(A),  max_value-V1) :- concept(neg(A)),   eval(A,V1).


% find the largest truth degree for the left-hand-side concept of query 
:~ query(C,_,_), eval(C,V). [-1@V+2, C,V]

% verify if there is a counterexample for the right-hand-side concept of the query
:~ query(_,D,Alpha), eval(D,V), @lt(V,max_value, Alpha) = 1. [-1@1, D,Alpha,V] 

#show.
#show eval(C,V) : eval(C,V), class(C).
#show query_true (VC,VD) : query(C,D,Alpha), eval(C,VC), eval(D,VD), @lt(VD,max_value, Alpha) != 1.
#show query_false(VC,VD) : query(C,D,Alpha), eval(C,VC), eval(D,VD), @lt(VD,max_value, Alpha) =  1.

% support exactly-one constraints encoded as exactly_one(ID). exactly_one(ID,Concept). ... exactly_one(ID,Concept).
:- exactly_one(ID), #count{Concept : exactly_one(ID,Concept), eval(Concept,max_value)} != 1.

% prevent these warnings
exactly_one(0) :- #false.
exactly_one(0,0) :- #false.
query(0,0,0) :- #false.
"""


@dataclasses.dataclass(frozen=True)
class Controller:
    network: NetworkTopology
    val_phi: List[float] = dataclasses.field(default_factory=lambda: Controller.default_val_phi())
    raw_code: str = dataclasses.field(default="")
    max_stable_models: int = dataclasses.field(default=0)

    QueryResult = namedtuple("QueryResult", "query_true left_concept_value right_concept_value threshold eval_values")

    def __post_init__(self):
        utils.validate("max_value", self.max_value, min_value=1, max_value=1000)
        utils.validate("val_phi", self.val_phi, equals=sorted(self.val_phi))

    @staticmethod
    def default_val_phi() -> List[float]:
        return [-10987, -4237, 0, 4236, 10986]

    @property
    def max_value(self) -> int:
        return len(self.val_phi)

    def __setup_control(self, query: Optional[str] = None):
        control = clingo.Control()
        control.configuration.solve.models = self.max_stable_models if query is None else 0
        control.add("base", ["max_value"], BASE_PROGRAM + '\n'.join(self.network_topology_as_facts(self.network))
                    + self.raw_code + ("" if query is None else f"query({query})."))
        self.__register_propagators(control)
        control.ground([("base", [Number(self.max_value)])], context=Context())
        return control

    @staticmethod
    def __read_eval(model) -> Dict:
        res = {}
        for symbol in model:
            if symbol.name == "eval":
                concept, value = symbol.arguments
                if concept.name == "bias":
                    continue
                layer, node = concept.name[1:].split('_', maxsplit=1)
                res[(int(layer), int(node))] = value.number
        return res

    def find_solutions(self) -> List[Dict]:
        control = self.__setup_control()
        model_collect = ModelCollect()
        control.solve(on_model=model_collect)
        return [self.__read_eval(model) for model in model_collect]

    def answer_query(self, query: str) -> QueryResult:
        utils.validate("query", query, custom=[utils.pattern(r"[^#]+#[^#]+#(1|1.0|0\.\d+)")])
        left, right, threshold = query.split('#')
        control = self.__setup_control(f"{left},{right},\"{threshold}\"")

        last_model = LastModel()
        control.solve(on_model=last_model)

        if last_model.has():
            model = last_model.get()
            eval_values = self.__read_eval(model)
            for symbol in model:
                if symbol.name in ["query_false", "query_true"]:
                    return self.QueryResult(
                        query_true=symbol.name == "query_true",
                        left_concept_value=symbol.arguments[0].number / self.max_value,
                        right_concept_value=symbol.arguments[1].number / self.max_value,
                        threshold=threshold,
                        eval_values=eval_values,
                    )
        return self.QueryResult(query_true=None, left_concept_value=None, right_concept_value=None, threshold=None,
                                eval_values=None)

    def __register_propagators(self, control):
        for layer_index, _ in enumerate(range(1, self.network.number_of_layers()), start=2):
            for node_index, _ in enumerate(range(self.network.number_of_nodes(layer=layer_index)), start=1):
                control.register_propagator(ValPhiPropagator(f"l{layer_index}_{node_index}", val_phi=self.val_phi))

    @staticmethod
    def network_topology_as_facts(network: NetworkTopology) -> List[str]:
        res = []
        for layer_index, _ in enumerate(range(network.number_of_layers()), start=1):
            for node_index, _ in enumerate(range(network.number_of_nodes(layer=layer_index)), start=1):
                weights = network.in_weights(layer=layer_index, node=node_index)
                if weights:
                    res.append(f"sub_type(l{layer_index}_{node_index},bias(l{layer_index - 1}),\"{weights[0]}\").")
                    for weight_index, weight in enumerate(weights[1:], start=1):
                        res.append(
                            f"sub_type(l{layer_index}_{node_index},l{layer_index - 1}_{weight_index},\"{weight}\").")
        for index in range(network.number_of_exactly_one()):
            nodes = network.nodes_in_exactly_one(index)
            res.append(f"exactly_one({index}).")
            for node in nodes:
                res.append(f"exactly_one({index},l1_{node}).")
        return res