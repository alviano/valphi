import dataclasses
from collections import namedtuple
from typing import List, Dict, Optional, Final

import clingo
from clingo.symbol import Number

from valphi import utils
from valphi.contexts import Context
from valphi.models import ModelCollect, LastModel
from valphi.networks import NetworkTopology, MaxSAT, NetworkInterface


@dataclasses.dataclass(frozen=True)
class Controller:
    network: NetworkInterface
    val_phi: List[float] = dataclasses.field(default_factory=lambda: Controller.default_val_phi())
    raw_code: str = dataclasses.field(default="")
    max_stable_models: int = dataclasses.field(default=0)
    use_wc: bool = dataclasses.field(default=False)
    use_ordered_encoding: bool = dataclasses.field(default=False)

    QueryResult = namedtuple("QueryResult", "query_true left_concept_value right_concept_value threshold eval_values")

    def __post_init__(self):
        utils.validate("max_value", self.max_value, min_value=1, max_value=1000)
        utils.validate("val_phi", self.val_phi, equals=sorted(self.val_phi))
        if type(self.network) is MaxSAT:
            utils.validate("", self.val_phi, equals=self.network.val_phi)

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
        control.add("base", ["max_value"], BASE_PROGRAM
                    + (QUERY_ENCODING if query and not self.use_ordered_encoding else "")
                    + (QUERY_ORDERED_ENCODING if query and self.use_ordered_encoding else "")
                    + (ORDERED_ENCODING if self.use_ordered_encoding else "")
                    + '\n'.join(self.network.network_facts.as_strings)
                    + self.raw_code + ("" if query is None else f"query({query})."))
        control.ground([("base", [Number(self.max_value)])], context=Context())
        if self.use_wc:
            constraints = self.__generate_wc()
            control.add("base", ["max_value"], '\n'.join(constraints))
            control.ground([("base", [Number(self.max_value)])], context=Context())
        else:
            self.network.register_propagators(control, self.val_phi)
        return control

    def __read_eval(self, model) -> Dict:
        res = {}
        for symbol in model:
            if symbol.name == "eval":
                concept, value = symbol.arguments
                if concept.name == "top":
                    continue
                if type(self.network) is NetworkTopology:
                    layer, node = concept.name[1:].split('_', maxsplit=1)
                    res[(int(layer), int(node))] = value.number
                else:
                    res[str(concept)] = value.number
        return res

    def find_solutions(self) -> List[Dict]:
        if type(self.network) is MaxSAT:
            raise ValueError("Use 'query even' for MaxSAT")
        control = self.__setup_control()
        model_collect = ModelCollect()
        control.solve(on_model=model_collect)
        return [self.__read_eval(model) for model in model_collect]

    def answer_query(self, query: str) -> QueryResult:
        if type(self.network) is MaxSAT:
            utils.validate("query", query, equals="even")
            query = self.network.query
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

    def __generate_wc(self):
        res = [f"val_phi(0,#inf,{self.val_phi[0]})."]
        for value in range(len(self.val_phi) - 1):
            res.append(f"val_phi({value + 1},{self.val_phi[value]},{self.val_phi[value + 1]}).")
        res.append(f"val_phi({len(self.val_phi)},{self.val_phi[-1]},#sup).")
        if self.use_ordered_encoding:
            res.append(WC_ORDERED_ENCODING)
        else:
            res.append(WC_ENCODING)
        return res


BASE_PROGRAM: Final = """
% let's use max_value+1 truth degrees of the form 0/max_value ... max_value/max_value
truth_degree(0..max_value).

% concepts from the network topology
concept(C) :- sub_type(C,_,_).
concept(C) :- sub_type(_,C,_).

% top class contains everything
concept(top).
eval(top,max_value).

% bot class contains nothing
concept(bot).
eval(bot,0).

% guess evaluation (optimize for crisp concepts)
{eval(C,V) : truth_degree(V)} = 1 :- concept(C), @is_named_concept(C) = 1, not crisp(C).
{eval(C,0); eval(C,max_value)} = 1 :- concept(C), @is_named_concept(C) = 1, crisp(C).
:- concept(C), @is_named_concept(C) != 1, crisp(C); not eval(C,0), not eval(C,max_value).

% all relevant concepts for the query
concept(impl(C,D)) :- query(C,D,_).
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

% support exactly-one constraints encoded as exactly_one(ID). exactly_one_element(ID,Concept). ... exactly_one_element(ID,Concept).
:- exactly_one(ID), #count{Concept : exactly_one_element(ID,Concept), eval(Concept,max_value)} != 1.

#show.
#show eval(C,V) : eval(C,V), concept(C), @is_named_concept(C) = 1.
#show query_true (V,V') : query(C,D,Alpha), eval(C,V), eval(impl(C,D),V'), @lt(V',max_value, Alpha) != 1.
#show query_false(V,V') : query(C,D,Alpha), eval(C,V), eval(impl(C,D),V'), @lt(V',max_value, Alpha) =  1.

% prevent these warnings
crisp(0) :- #false.
attack(0,0,0) :- #false.
exactly_one(0) :- #false.
exactly_one_element(0,0) :- #false.
query(0,0,0) :- #false.
"""

QUERY_ENCODING: Final = """
% find the largest truth degree for the left-hand-side concept of query 
:~ query(C,_,_), eval(C,V), V > 0. [-1@V+1, C,V]

% verify if there is a counterexample for the right-hand-side concept of the query
:~ query(C,D,Alpha), eval(impl(C,D),V), @lt(V,max_value, Alpha) = 1. [-1@1, C,D,Alpha,V] 
"""

QUERY_ORDERED_ENCODING: Final = """
% find the largest truth degree for the left-hand-side concept of query 
:~ query(C,_,_), eval_ge(C,V). [-1@2, C,V]

% verify if there is a counterexample for the right-hand-side concept of the query
:~ query(C,D,Alpha), eval(impl(C,D),V), @lt(V,max_value, Alpha) = 1. [-1@1, C,D,Alpha,V] 
"""

ORDERED_ENCODING: Final = """
{eval_ge(C,V) : truth_degree(V), V > 0} :- concept(C).
:- eval_ge(C,V), V > 1, not eval_ge(C,V-1).
:- concept(C), eval(C,V), V > 0, not eval_ge(C,V).
:- concept(C), eval_ge(C,V), not eval_ge(C,V+1), not eval(C,V).
:- concept(C), not eval_ge(C,1), not eval(C,0).

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
:- concept(neg(A)), truth_degree(V), V > 0; not eval_ge(A,max_value-V+1); not eval_ge(neg(A),V).

% A->B>=V <=> A<=B or B>=V
premise_greater_than_conclusion(A,B) :-
    concept(impl(A,B));
    eval_ge(A,V);
    not eval_ge(B,V).
:- concept(impl(A,B)); eval_ge(impl(A,B),V); premise_greater_than_conclusion(A,B); not eval_ge(B,V).
:- concept(impl(A,B)), truth_degree(V), V > 0; not premise_greater_than_conclusion(A,B); not eval_ge(impl(A,B),V).
:- concept(impl(A,B)); eval_ge(B,V); not eval_ge(impl(A,B),V).
"""

WC_ENCODING: Final = """
:- truth_degree(V), val_phi(V,LB,UB);
   sub_type(C,_,_);
   LB < #sum{
       @str_to_int(W) * VD,D,VD : sub_type(C,D,W), eval(D,VD), VD > 0
   } <= UB;
   not eval(C,V).
:- truth_degree(V), val_phi(V,LB,UB);
   sub_type(C,_,_);
   not LB < #sum{
       @str_to_int(W) * VD,D,VD : sub_type(C,D,W), eval(D,VD), VD > 0
   } <= UB;
   eval(C,V).
"""

# WC_ORDERED_ENCODING: Final = """
# :- truth_degree(V), val_phi(V,LB,UB);
#    sub_type(C,_,_);
#    LB < #sum{
#        @str_to_int(W),D,VD : sub_type(C,D,W), eval_ge(D,VD)
#    } <= UB;
#    not eval(C,V).
# :- truth_degree(V), val_phi(V,LB,UB);
#    sub_type(C,_,_);
#    not LB < #sum{
#        @str_to_int(W),D,VD : sub_type(C,D,W), eval_ge(D,VD)
#    } <= UB;
#    eval(C,V).
# """
WC_ORDERED_ENCODING: Final = """
:- truth_degree(V), V > 0, val_phi(V,LB,UB);
   sub_type(C,_,_);
   #sum{
       @str_to_int(W),D,VD : sub_type(C,D,W), eval_ge(D,VD)
   } > LB;
   not eval_ge(C,V).
:- truth_degree(V), V > 0, val_phi(V,LB,UB);
   sub_type(C,_,_);
   not #sum{
       @str_to_int(W),D,VD : sub_type(C,D,W), eval_ge(D,VD)
   } > LB;
   eval_ge(C,V).
"""
