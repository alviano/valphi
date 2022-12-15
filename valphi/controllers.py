import dataclasses
from collections import namedtuple
from typing import List, Dict, Optional, Union, Final

import clingo
from clingo.symbol import Number

from valphi import utils
from valphi.contexts import Context
from valphi.models import ModelCollect, LastModel
from valphi.networks import NetworkTopology, ArgumentationGraph
from valphi.propagators import ValPhiPropagator


@dataclasses.dataclass(frozen=True)
class Controller:
    network: Union[NetworkTopology, ArgumentationGraph]
    val_phi: List[float] = dataclasses.field(default_factory=lambda: Controller.default_val_phi())
    raw_code: str = dataclasses.field(default="")
    max_stable_models: int = dataclasses.field(default=0)
    use_wc: bool = dataclasses.field(default=False)
    use_ordered_encoding: bool = dataclasses.field(default=False)

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
        # control = clingo.Control(["--opt-strategy=usc,k,4", "--opt-usc-shrink=rgs"] if query else [])
        control = clingo.Control()
        control.configuration.solve.models = self.max_stable_models if query is None else 0
        control.add("base", ["max_value"], BASE_PROGRAM + (ORDERED_ENCODING if self.use_ordered_encoding else "")
                    + '\n'.join(self.network_topology_as_facts(self.network))
                    + self.raw_code + ("" if query is None else f"query({query})."))
        control.ground([("base", [Number(self.max_value)])], context=Context())
        if self.use_wc:
            constraints = self.__generate_wc(control)
            control.add("base", ["max_value"], '\n'.join(constraints))
            control.ground([("base", [Number(self.max_value)])], context=Context())
        else:
            self.__register_propagators(control)
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
        if type(self.network) is ArgumentationGraph:
            for attacked in self.network.compute_attacked():
                control.register_propagator(ValPhiPropagator(f"l{attacked}_1", val_phi=self.val_phi))
        else:
            for layer_index, _ in enumerate(range(1, self.network.number_of_layers()), start=2):
                for node_index, _ in enumerate(range(self.network.number_of_nodes(layer=layer_index)), start=1):
                    control.register_propagator(ValPhiPropagator(f"l{layer_index}_{node_index}", val_phi=self.val_phi))

    def __generate_wc(self, control):
        res = [f"val_phi(0,none,{self.val_phi[0]})."]
        for value in range(len(self.val_phi) - 1):
            res.append(f"val_phi({value + 1},{self.val_phi[value]},{self.val_phi[value + 1]}).")
        res.append(f"val_phi({len(self.val_phi)},{self.val_phi[-1]},none).")
        if self.use_ordered_encoding:
            res.append(WC_ORDERED_ENCODING)
        else:
            res.append(WC_ENCODING)
        return res

    @classmethod
    def network_topology_as_facts(cls, network: Union[NetworkTopology, ArgumentationGraph]) -> List[str]:
        if type(network) is ArgumentationGraph:
            return cls.argumentation_graph_as_facts(network)
        res = ["binary_input."]
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

    @staticmethod
    def argumentation_graph_as_facts(graph: ArgumentationGraph) -> List[str]:
        return [f"attack(l{attacker}_1, l{attacked}_1, \"{weight}\")." for (attacker, attacked, weight) in graph]


BASE_PROGRAM: Final = """
% let's use max_value+1 truth degrees of the form 0/max_value ... max_value/max_value
val(0..max_value).

sub_type(Attacked, Attacker, Weight) :- attack(Attacker, Attacked, Weight).


% classes from the network topology
class(C) :- sub_type(C,_,_).
class(C) :- sub_type(_,C,_).

% inputs have binary values (biases fixed to max_value)
{eval(C,0); eval(C,max_value)} = 1 :- binary_input; class(C), not sub_type(C,_,_); C != bias(ID) : class(bias(ID)).
eval(bias(ID),max_value) :- class(bias(ID)), not sub_type(bias(ID),_,_).
% or possibly not!
{eval(C,V) : val(V)} = 1 :- not binary_input; class(C), not sub_type(C,_,_); C != bias(ID) : class(bias(ID)).

% other classes take some value
{eval(C,V) : val(V)} = 1 :- class(C), sub_type(C,_,_).


% all relevant concept for the query
concept(impl(C,D)) :- query(C,D,_).
% concept(C) :- query(C,D,_).
% concept(D) :- query(C,D,_).
concept(A) :- concept(and(A,B)).
concept(B) :- concept(and(A,B)).
concept(A) :- concept(or(A,B)).
concept(B) :- concept(or(A,B)).
concept(A) :- concept(neg(A)).
concept(A) :- concept(impl(A,B)).
concept(B) :- concept(impl(A,B)).

% Godel evaluation of complex concepts
eval(and(A,B),@min(V1,V2))  :- concept(and(A,B)), eval(A,V1), eval(B,V2).
eval( or(A,B),@max(V1,V2))  :- concept( or(A,B)), eval(A,V1), eval(B,V2).
eval(neg(A),  max_value-V1) :- concept(neg(A)),   eval(A,V1).
eval(impl(A,B), @godel_implication(V1,V2, max_value))
                            :- concept(impl(A,B)), eval(A,V1), eval(B,V2).

% find the largest truth degree for the left-hand-side concept of query 
:~ query(C,_,_), eval(C,V). [-1@V+2, C,V]

% verify if there is a counterexample for the right-hand-side concept of the query
:~ query(C,D,Alpha), eval(impl(C,D),V), @lt(V,max_value, Alpha) = 1. [-1@1, D,Alpha,V] 
% :~ query(_,D,Alpha), eval(D,V), @lt(V,max_value, Alpha) = 1. [-1@1, D,Alpha,V] 

#show.
#show eval(C,V) : eval(C,V), class(C).
#show query_true (VC,VD) : query(C,D,Alpha), eval(C,VC), eval(impl(C,D),VD), @lt(VD,max_value, Alpha) != 1.
#show query_false(VC,VD) : query(C,D,Alpha), eval(C,VC), eval(impl(C,D),VD), @lt(VD,max_value, Alpha) =  1.
% #show query_true (VC,VD) : query(C,D,Alpha), eval(C,VC), eval(D,VD), @lt(VD,max_value, Alpha) != 1.
% #show query_false(VC,VD) : query(C,D,Alpha), eval(C,VC), eval(D,VD), @lt(VD,max_value, Alpha) =  1.

% support exactly-one constraints encoded as exactly_one(ID). exactly_one(ID,Concept). ... exactly_one(ID,Concept).
:- exactly_one(ID), #count{Concept : exactly_one(ID,Concept), eval(Concept,max_value)} != 1.

% prevent these warnings
binary_input :- #false.
attack(0,0,0) :- #false.
exactly_one(0) :- #false.
exactly_one(0,0) :- #false.
query(0,0,0) :- #false.
"""

ORDERED_ENCODING: Final = """
concept_or_class(C) :- class(C).
concept_or_class(C) :- concept(C).

{eval_ge(C,V) : val(V), V > 0} :- concept_or_class(C).
:- eval_ge(C,V), V > 1, not eval_ge(C,V-1).
:- concept_or_class(C), eval(C,V), V > 0, not eval_ge(C,V).
:- concept_or_class(C), eval_ge(C,V), not eval_ge(C,V+1), not eval(C,V).
:- concept_or_class(C), not eval_ge(C,1), not eval(C,0).

% A&B>=V <=> A>=V and B>=V 
:- concept(and(A,B)), eval_ge(and(A,B),V); not eval_ge(A,V).
:- concept(and(A,B)), eval_ge(and(A,B),V); not eval_ge(B,V).
:- concept(and(A,B)), eval_ge(A,V), eval_ge(B,V); not eval_ge(and(A,B),V).

% A|B>=V <=> A>=V or B>=V
:- concept(or(A,B)), eval_ge(or(A,B),V); not eval_ge(A,V), not eval_ge(B,V).
:- concept(or(A,B)), eval_ge(A,V); not eval_ge(or(A,B),V).
:- concept(or(A,B)), eval_ge(B,V); not eval_ge(or(A,B),V).

% ¬A>=V <=> A<=max_value-V
:- concept(neg(A)); eval_ge(neg(A),V); eval_ge(A,max_value-V+1).
:- concept(neg(A)), val(V), V > 0; not eval_ge(A,max_value-V+1); not eval_ge(neg(A),V).

% A->B>=V <=> A<=B or B>=V
premise_greater_than_conclusion(A,B) :-
    concept(impl(A,B));
    eval_ge(A,V);
    not eval_ge(B,V).
:- concept(impl(A,B)); eval_ge(impl(A,B),V); premise_greater_than_conclusion(A,B); not eval_ge(B,V).
:- concept(impl(A,B)), val(V), V > 0; not premise_greater_than_conclusion(A,B); not eval_ge(impl(A,B),V).
:- concept(impl(A,B)); eval_ge(B,V); not eval_ge(impl(A,B),V).
"""

WC_ENCODING: Final = """
:- val(V), V > 0, V < max_value; val_phi(V,LB,UB);
   sub_type(C,_,_);
   LB < #sum{
       @str_to_int(W) * VD,D,VD : sub_type(C,D,W), eval(D,VD), VD > 0
   } <= UB;
   not eval(C,V).
:- val(V), V > 0, V < max_value; val_phi(V,LB,UB);
   sub_type(C,_,_);
   not LB < #sum{
       @str_to_int(W) * VD,D,VD : sub_type(C,D,W), eval(D,VD), VD > 0
   } <= UB;
   eval(C,V).

:- val(V), V = 0; val_phi(V,LB,UB);
   sub_type(C,_,_);
   #sum{
       @str_to_int(W) * VD,D,VD : sub_type(C,D,W), eval(D,VD), VD > 0
   } <= UB;
   not eval(C,V).
:- val(V), V = 0; val_phi(V,LB,UB);
   sub_type(C,_,_);
   not #sum{
       @str_to_int(W) * VD,D,VD : sub_type(C,D,W), eval(D,VD), VD > 0
   } <= UB;
   eval(C,V).

:- val(V), V = max_value; val_phi(V,LB,UB);
   sub_type(C,_,_);
   LB < #sum{
       @str_to_int(W) * VD,D,VD : sub_type(C,D,W), eval(D,VD), VD > 0
   };
   not eval(C,V).
:- val(V), V = max_value; val_phi(V,LB,UB);
   sub_type(C,_,_);
   not LB < #sum{
       @str_to_int(W) * VD,D,VD : sub_type(C,D,W), eval(D,VD), VD > 0
   };
   eval(C,V).
"""

WC_ORDERED_ENCODING: Final = """
:- val(V), V > 0, V < max_value; val_phi(V,LB,UB);
   sub_type(C,_,_);
   LB < #sum{
       @str_to_int(W),D,VD : sub_type(C,D,W), eval_ge(D,VD)
   } <= UB;
   not eval(C,V).
:- val(V), V > 0, V < max_value; val_phi(V,LB,UB);
   sub_type(C,_,_);
   not LB < #sum{
       @str_to_int(W),D,VD : sub_type(C,D,W), eval_ge(D,VD)
   } <= UB;
   eval(C,V).

:- val(V), V = 0; val_phi(V,LB,UB);
   sub_type(C,_,_);
   #sum{
       @str_to_int(W),D,VD : sub_type(C,D,W), eval_ge(D,VD)
   } <= UB;
   not eval(C,V).
:- val(V), V = 0; val_phi(V,LB,UB);
   sub_type(C,_,_);
   not #sum{
       @str_to_int(W),D,VD : sub_type(C,D,W), eval_ge(D,VD)
   } <= UB;
   eval(C,V).

:- val(V), V = max_value; val_phi(V,LB,UB);
   sub_type(C,_,_);
   LB < #sum{
       @str_to_int(W),D,VD : sub_type(C,D,W), eval_ge(D,VD)
   };
   not eval(C,V).
:- val(V), V = max_value; val_phi(V,LB,UB);
   sub_type(C,_,_);
   not LB < #sum{
       @str_to_int(W),D,VD : sub_type(C,D,W), eval_ge(D,VD)
   };
   eval(C,V).
"""
