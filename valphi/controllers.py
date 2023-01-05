import dataclasses
from typing import List, Optional, Final, Union

import clingo
import typeguard
from clingo.symbol import Number
from pydot import frozendict

from valphi import utils
from valphi.contexts import Context
from valphi.models import ModelCollect, LastModel
from valphi.networks import NetworkTopology, MaxSAT, NetworkInterface


@typeguard.typechecked
@dataclasses.dataclass(frozen=True)
class Controller:
    network: NetworkInterface
    val_phi: List[float] = dataclasses.field(default_factory=lambda: Controller.default_val_phi())
    raw_code: str = dataclasses.field(default="")
    max_stable_models: int = dataclasses.field(default=0)
    use_wc: bool = dataclasses.field(default=False)
    use_ordered_encoding: bool = dataclasses.field(default=False)

    @typeguard.typechecked
    @dataclasses.dataclass(frozen=True)
    class QueryTrue:
        threshold: float
        left_concept_value: float
        assignment: frozendict = dataclasses.field(default_factory=frozendict)

        @property
        def true(self):
            return True

        @property
        def false(self):
            return False

    @typeguard.typechecked
    @dataclasses.dataclass(frozen=True)
    class QueryFalse:
        threshold: float
        typical_individual: str
        left_concept_value: float
        right_concept_value: float
        assignment: frozendict = dataclasses.field(default_factory=frozendict)

        @property
        def true(self):
            return False

        @property
        def false(self):
            return True

    def __post_init__(self):
        utils.validate("max_value", self.max_value, min_value=1, max_value=1000)
        utils.validate("val_phi", self.val_phi, equals=sorted(self.val_phi))
        utils.validate("val-phi must be integer", all(type(value) is int or value.is_integer()
                                                      for value in self.val_phi),
                       equals=True,
                       help_msg="Weight-constraints requires an integer val-phi")
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

    def __read_eval(self, model) -> frozendict:
        res = {}
        for symbol in model:
            if symbol.name == "eval":
                concept, individual, value = symbol.arguments
                if concept.name in ["top", "bot"]:
                    continue
                if type(self.network) is NetworkTopology:
                    layer, node = concept.name[1:].split('_', maxsplit=1)
                    res[(int(layer), int(node))] = value.number
                else:
                    res[f"{concept}({individual})"] = f"{value.number}/{self.max_value}"
        return frozendict(res)

    def find_solutions(self) -> List[frozendict]:
        if type(self.network) is MaxSAT:
            raise ValueError("Use 'query even' for MaxSAT")
        control = self.__setup_control()
        model_collect = ModelCollect()
        control.solve(on_model=model_collect)
        return [self.__read_eval(model) for model in model_collect]

    def answer_query(self, query: str) -> Union[QueryTrue, QueryFalse]:
        if type(self.network) is MaxSAT:
            utils.validate("query", query, equals="even")
            query = self.network.query
        utils.validate("query", query, custom=[utils.pattern(r"[^#]+#[^#]+#(1|1.0|0\.\d+)")],
                       help_msg=f'The query "{query}" is not in the expected format. Is it a filename?')
        left, right, threshold = query.split('#')
        control = self.__setup_control(f'{left},{right},">=","{threshold}"')

        last_model = LastModel()
        control.solve(on_model=last_model)

        if last_model.has():
            model = last_model.get()
            eval_values = self.__read_eval(model)
            for symbol in model:
                if symbol.name == "query_false":
                    return self.QueryFalse(
                        threshold=float(threshold),
                        typical_individual=str(symbol.arguments[0]),
                        left_concept_value=symbol.arguments[1].number / self.max_value,
                        right_concept_value=symbol.arguments[2].number / self.max_value,
                        assignment=eval_values,
                    )
                elif symbol.name == "query_true":
                    return self.QueryTrue(
                        threshold=float(threshold),
                        left_concept_value=symbol.arguments[0].number / self.max_value,
                        assignment=eval_values,
                    )

    def __generate_wc(self):
        res = [f"val_phi(0,#inf,{int(self.val_phi[0])})."]
        for value in range(len(self.val_phi) - 1):
            res.append(f"val_phi({value + 1},{int(self.val_phi[value])},{int(self.val_phi[value + 1])}).")
        res.append(f"val_phi({len(self.val_phi)},{int(self.val_phi[-1])},#sup).")
        if self.use_ordered_encoding:
            res.append(WC_ORDERED_ENCODING)
        else:
            res.append(WC_ENCODING)
        return res


BASE_PROGRAM: Final = """
% let's use max_value+1 truth degrees of the form 0/max_value ... max_value/max_value
truth_degree(0..max_value).

% anonymous individual (to enforce nonempty set of individuals)
individual(anonymous).

% concepts from weighted typicality inclusions
concept(C) :- weighted_typicality_inclusion(C,_,_).
concept(C) :- weighted_typicality_inclusion(_,C,_).

% concepts and individuals from TBox and ABox
concept(impl(C,D)) :- concept_inclusion(C,D,_,_).
concept(C) :- assertion(C,_,_,_).
individual(X) :- assertion(_,X,_,_).

% concepts from the query
concept(impl(C,D)) :- query(C,D,_,_).

% sub-concepts
concept(A) :- concept(and(A,B)).
concept(B) :- concept(and(A,B)).
concept(A) :- concept(or(A,B)).
concept(B) :- concept(or(A,B)).
concept(A) :- concept(neg(A)).
concept(A) :- concept(impl(A,B)).
concept(B) :- concept(impl(A,B)).

% top class contains everything
concept(top).
eval(top,X,max_value) :- individual(X).

% bot class contains nothing
concept(bot).
eval(bot,X,0) :- individual(X).

% guess evaluation (optimize for crisp concepts)
{eval(C,X,V) : truth_degree(V)} = 1 :- concept(C), individual(X), @is_named_concept(C) = 1, not crisp(C).
{eval(C,X,0); eval(C,X,max_value)} = 1 :- concept(C), individual(X), @is_named_concept(C) = 1, crisp(C).
:- concept(C), @is_named_concept(C) != 1, crisp(C); individual(X), not eval(C,X,0), not eval(C,X,max_value).

% Godel evaluation of complex concepts
eval(and(A,B), X, @min(V1,V2))  :- concept(and(A,B)), individual(X), eval(A,X,V1), eval(B,X,V2).
eval( or(A,B), X, @max(V1,V2))  :- concept( or(A,B)), individual(X), eval(A,X,V1), eval(B,X,V2).
eval(neg(A),   X, max_value-V1) :- concept(neg(A)),   individual(X), eval(A,X,V1).
eval(impl(A,B),X, @implication(V1,V2, max_value))
    :- concept(impl(A,B)), individual(X), eval(A,X,V1), eval(B,X,V2).

% TBox and ABox axioms
:- concept_inclusion(C,D,Operator,Alpha), Operator = ">="; 
    eval(impl(C,D),X,V), @ge(V,max_value, Alpha) != 1.
:- concept_inclusion(C,D,Operator,Alpha), Operator = ">"; 
    eval(impl(C,D),X,V), @gt(V,max_value, Alpha) != 1.
:- concept_inclusion(C,D,Operator,Alpha), Operator = "<="; 
    #count{X : individual(X), eval(impl(C,D),X,V), @le(V,max_value, Alpha) = 1} = 0.
:- concept_inclusion(C,D,Operator,Alpha), Operator = "<"; 
    #count{X : individual(X), eval(impl(C,D),X,V), @lt(V,max_value, Alpha) = 1} = 0.
concept_inclusion(C,D,">=",Alpha) :- concept_inclusion(C,D,Operator,Alpha), Operator = "=". 
concept_inclusion(C,D,"<=",Alpha) :- concept_inclusion(C,D,Operator,Alpha), Operator = "=". 
:- concept_inclusion(C,D,Operator,Alpha), Operator = "!=";
    #count{X : individual(X), eval(impl(C,D),X,V), @lt(V,max_value, Alpha) = 1} = 0;
    eval(impl(C,D),_,V), @gt(V,max_value, Alpha) != 1.
:- assertion(C,X,Operator,Alpha); eval(C,X,V), @apply_operator(V,max_value, Operator,Alpha) != 1.

% support exactly-one constraints encoded as exactly_one(ID). exactly_one_element(ID,Concept). ... exactly_one_element(ID,Concept).
:- exactly_one(ID), individual(X), #count{Concept : exactly_one_element(ID,Concept), eval(Concept,X,max_value)} != 1.

% verify if there is a counterexample for the right-hand-side concept of the query
typical_element(C,X) :- query(C,_,_,_), eval(C,X,V), V = #max{V' : eval(C,X',V')}.
query_false(X,V) :- query(C,D,Operator,Alpha), typical_element(C,X);
   eval(impl(C,D),X,V), @apply_operator(V,max_value, Operator,Alpha) != 1.
:~ query_false(_,_). [-1@1] 


#show.
#show eval(C,X,V) : eval(C,X,V), concept(C), @is_named_concept(C) = 1.
#show query_true (V) : not query_false(_,_), query(C,D,_,Alpha), typical_element(C,X), eval(C,X,V).
#show query_false(X,V,V') :  query_false(_,_), query(C,D,_,Alpha), typical_element(C,X), eval(C,X,V), eval(impl(C,D),X,V').

% prevent these warnings
individual(0) :- #false.
crisp(0) :- #false.
attack(0,0,0) :- #false.
exactly_one(0) :- #false.
exactly_one_element(0,0) :- #false.
query(0,0,0,0) :- #false.
concept_inclusion(0,0,0,0) :- #false.
assertion(0,0,0,0) :- #false.
weighted_typicality_inclusion(0,0,0) :- #false.
"""

QUERY_ENCODING: Final = """
% find the largest truth degree for the left-hand-side concept of query 
:~ query(C,_,_,_), eval(C,X,V), V > 0. [-1@V+1]
"""

QUERY_ORDERED_ENCODING: Final = """
% find the largest truth degree for the left-hand-side concept of query 
:~ query(C,_,_,_), eval_ge(C,X,V). [-1@2, V]
"""

ORDERED_ENCODING: Final = """
{eval_ge(C,X,V) : truth_degree(V), V > 0} :- concept(C), individual(X).
:- eval_ge(C,X,V), V > 1, not eval_ge(C,X,V-1).
:- concept(C), individual(X), eval(C,X,V), V > 0, not eval_ge(C,X,V).
:- concept(C), individual(X), eval_ge(C,X,V), not eval_ge(C,X,V+1), not eval(C,X,V).
:- concept(C), individual(X), not eval_ge(C,X,1), not eval(C,X,0).

% A&B>=V <=> A>=V and B>=V 
:- concept(and(A,B)), individual(X), eval_ge(and(A,B),X,V); not eval_ge(A,X,V).
:- concept(and(A,B)), individual(X), eval_ge(and(A,B),X,V); not eval_ge(B,X,V).
:- concept(and(A,B)), individual(X), eval_ge(A,X,V), eval_ge(B,X,V); not eval_ge(and(A,B),X,V).

% A|B>=V <=> A>=V or B>=V
:- concept(or(A,B)), individual(X), eval_ge(or(A,B),X,V); not eval_ge(A,X,V), not eval_ge(B,X,V).
:- concept(or(A,B)), individual(X), eval_ge(A,X,V); not eval_ge(or(A,B),X,V).
:- concept(or(A,B)), individual(X), eval_ge(B,X,V); not eval_ge(or(A,B),X,V).

% ¬A>=V <=> A<=max_value-V
:- concept(neg(A)), individual(X); eval_ge(neg(A),X,V); eval_ge(A,X,max_value-V+1).
:- concept(neg(A)), individual(X), truth_degree(V), V > 0; not eval_ge(A,X,max_value-V+1); not eval_ge(neg(A),X,V).

% A->B>=V <=> A<=B or B>=V
premise_greater_than_conclusion(A,B,X) :-
    concept(impl(A,B)), individual(X);
    eval_ge(A,X,V);
    not eval_ge(B,X,V).
:- concept(impl(A,B)), individual(X); eval_ge(impl(A,B),X,V); premise_greater_than_conclusion(A,B,X); not eval_ge(B,X,V).
:- concept(impl(A,B)), individual(X), truth_degree(V), V > 0; not premise_greater_than_conclusion(A,B,X); not eval_ge(impl(A,B),X,V).
:- concept(impl(A,B)), individual(X); eval_ge(B,X,V); not eval_ge(impl(A,B),X,V).
"""

WC_ENCODING: Final = """
:- truth_degree(V), val_phi(V,LB,UB);
   weighted_typicality_inclusion(C,_,_), individual(X);
   LB < #sum{
       @str_to_int(W) * VD,D,VD : weighted_typicality_inclusion(C,D,W), eval(D,X,VD), VD > 0
   } <= UB;
   not eval(C,X,V).
:- truth_degree(V), val_phi(V,LB,UB);
   weighted_typicality_inclusion(C,_,_), individual(X);
   not LB < #sum{
       @str_to_int(W) * VD,D,VD : weighted_typicality_inclusion(C,D,W), eval(D,X,VD), VD > 0
   } <= UB;
   eval(C,X,V).
"""

# WC_ORDERED_ENCODING: Final = """
# :- truth_degree(V), val_phi(V,LB,UB);
#    weighted_typicality_inclusion(C,_,_), individual(X);
#    LB < #sum{
#        @str_to_int(W),D,VD : weighted_typicality_inclusion(C,D,W), eval_ge(D,X,VD)
#    } <= UB;
#    not eval(C,X,V).
# :- truth_degree(V), val_phi(V,LB,UB);
#    weighted_typicality_inclusion(C,_,_), individual(X);
#    not LB < #sum{
#        @str_to_int(W),D,VD : weighted_typicality_inclusion(C,D,W), eval_ge(D,X,VD)
#    } <= UB;
#    eval(C,X,V).
# """
WC_ORDERED_ENCODING: Final = """
:- truth_degree(V), V > 0, val_phi(V,LB,UB);
   weighted_typicality_inclusion(C,_,_), individual(X);
   #sum{
       @str_to_int(W),D,VD : weighted_typicality_inclusion(C,D,W), eval_ge(D,X,VD)
   } > LB;
   not eval_ge(C,X,V).
:- truth_degree(V), V > 0, val_phi(V,LB,UB);
   weighted_typicality_inclusion(C,_,_), individual(X);
   not #sum{
       @str_to_int(W),D,VD : weighted_typicality_inclusion(C,D,W), eval_ge(D,X,VD)
   } > LB;
   eval_ge(C,X,V).
"""
