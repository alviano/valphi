import dataclasses
from dataclasses import InitVar
from enum import Enum, auto
from typing import List, Optional, Final

import clingo
import typeguard
from clingo.symbol import Number
from dumbo_utils.primitives import PrivateKey
from dumbo_utils.validation import validate, pattern
from pydot import frozendict

from valphi.contexts import Context
from valphi.models import ModelCollect, LastModel
from valphi.networks import NetworkTopology, MaxSAT, NetworkInterface, ArgumentationGraph


@typeguard.typechecked
@dataclasses.dataclass(frozen=True)
class Controller:
    network: NetworkInterface
    val_phi: List[float] = dataclasses.field(default_factory=lambda: Controller.default_val_phi())
    raw_code: str = dataclasses.field(default="")
    use_wc: Optional[int] = dataclasses.field(default=None)
    use_ordered_encoding: bool = dataclasses.field(default=False)

    @typeguard.typechecked
    @dataclasses.dataclass(frozen=True)
    class QueryResult:
        key: InitVar[PrivateKey]
        true: bool
        consistent_knowledge_base: bool
        left_concept_value: Optional[float]
        assignment: frozendict = dataclasses.field(default_factory=frozendict)
        witness: bool = dataclasses.field(default=False)

        __key = PrivateKey()

        def __post_init__(self, key: PrivateKey):
            self.__key.validate(key)

        @property
        def false(self):
            return not self.true

        @staticmethod
        def of_true(left_concept_value: float, assignment: frozendict, witness: bool) -> 'Controller.QueryResult':
            return Controller.QueryResult(
                key=Controller.QueryResult.__key,
                true=True,
                consistent_knowledge_base=True,
                left_concept_value=left_concept_value,
                assignment=assignment,
                witness=witness,
            )

        @staticmethod
        def of_false(left_concept_value: float, assignment: frozendict, witness: bool) -> 'Controller.QueryResult':
            return Controller.QueryResult(
                key=Controller.QueryResult.__key,
                true=False,
                consistent_knowledge_base=True,
                left_concept_value=left_concept_value,
                assignment=assignment,
                witness=witness,
            )

        @staticmethod
        def of_inconsistent_knowledge_base() -> 'Controller.QueryResult':
            return Controller.QueryResult(
                key=Controller.QueryResult.__key,
                true=True,
                consistent_knowledge_base=False,
                left_concept_value=None,
            )

    def __post_init__(self):
        validate("max_value", self.max_value, min_value=1, max_value=1000)
        validate("val_phi", self.val_phi, equals=sorted(self.val_phi))
        if self.use_wc is not None:
            validate("use_wc", self.use_wc, min_value=1, max_value=1_000_000)
        # if self.use_wc:
        #     validate("val-phi must be integer", all(type(value) is int or value.is_integer() for value in self.val_phi),
        #              equals=True, help_msg="Weight-constraints requires an integer val-phi")
        if type(self.network) is MaxSAT:
            validate("", self.val_phi, equals=self.network.val_phi)

    @staticmethod
    def default_val_phi() -> List[float]:
        return [-10.987, -4.237, 0, 4.236, 10.986]

    @property
    def max_value(self) -> int:
        return len(self.val_phi)

    def __setup_control(self, query: Optional[str] = None):
        network = self.network if self.use_wc is None else self.network.approximate(self.use_wc)
        # control = clingo.Control(["--opt-strategy=usc,k,4", "--opt-usc-shrink=rgs"] if query else [])
        control = clingo.Control()
        # control.configuration.solve.models = self.max_stable_models if query is None else 0
        control.add("base", ["max_value"], BASE_PROGRAM
                    + (QUERY_ENCODING if query and not self.use_ordered_encoding else "")
                    + (QUERY_ORDERED_ENCODING if query and self.use_ordered_encoding else "")
                    + (ORDERED_ENCODING if self.use_ordered_encoding else "")
                    + network.network_facts.as_facts
                    + self.raw_code + ("" if query is None else f"query({query})."))
        control.ground([("base", [Number(self.max_value)])], context=Context())
        if self.use_wc:
            constraints = self.__generate_wc()
            control.add("base", ["max_value"], '\n'.join(constraints))
            control.ground([("base", [Number(self.max_value)])], context=Context())
        else:
            network.register_propagators(control, self.val_phi)
        return control

    def __read_eval(self, model) -> frozendict:
        res = {}
        for symbol in model:
            if symbol.predicate_name == "eval":
                concept, individual, value = symbol.arguments
                if concept.name in ["top", "bot"]:
                    continue
                if type(self.network) is NetworkTopology:
                    layer, node = concept.name[1:].split('_', maxsplit=1)
                    res[(int(layer), int(node))] = f"{value.number}/{self.max_value}"
                elif type(self.network) is ArgumentationGraph:
                    validate("format", concept.name, custom=[pattern(r"a[0-9]+")],
                             help_msg="The format of the argument is wrong")
                    validate("format", concept.arguments, length=0, help_msg="The format of the argument is wrong")
                    res[concept.name] = f"{value.number}/{self.max_value}"
                else:
                    res[f"{concept}({individual})"] = f"{value.number}/{self.max_value}"
        return frozendict(res)

    @staticmethod
    def __read_typical(model) -> int:
        for symbol in model:
            if symbol.predicate_name == "typical":
                return symbol.arguments[0].number

    def find_solutions(self, max_number_of_solutions: int = 0) -> List[frozendict]:
        validate('max_number_of_solutions', max_number_of_solutions, min_value=0)
        if type(self.network) is MaxSAT:
            raise ValueError("Use 'query even' for MaxSAT")
        control = self.__setup_control()
        control.configuration.solve.models = max_number_of_solutions
        model_collect = ModelCollect()
        control.solve(on_model=model_collect)
        return [self.__read_eval(model) for model in model_collect]

    def answer_query(self, query: str) -> "Controller.QueryResult":
        if type(self.network) is MaxSAT:
            validate("query", query, equals="even")
            query = self.network.query
        validate("query", query, custom=[pattern(r"[^#]+#[^#]+#(<|<=|>=|>)#(1|1.0|0\.\d+)")],
                 help_msg=f'The query "{query}" is not in the expected format. Is it a filename?')
        left, right, comparator, threshold = query.split('#')
        control = self.__setup_control(f'{left},{right},"{comparator}","{threshold}"')

        last_model = LastModel()
        control.solve(on_model=last_model)

        if not last_model.has():
            return self.QueryResult.of_inconsistent_knowledge_base()

        model = last_model.get()
        eval_values = self.__read_eval(model)
        left_concept_value = self.__read_typical(model)
        witness = len(model.filter(lambda atom: atom.predicate_name == "witness")) > 0
        factory_method = self.QueryResult.of_false if witness == (comparator in [">", ">="]) \
            else self.QueryResult.of_true
        return factory_method(
            left_concept_value=left_concept_value / self.max_value,
            assignment=eval_values,
            witness=witness,
        )

    def __generate_wc(self):
        val_phi = [round(value * self.use_wc) for value in self.val_phi]
        res = [f"val_phi(0,#inf,{int(val_phi[0])})."]
        for value in range(len(val_phi) - 1):
            res.append(f"val_phi({value + 1},{int(val_phi[value])},{int(val_phi[value + 1])}).")
        res.append(f"val_phi({len(val_phi)},{int(val_phi[-1])},#sup).")
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

% TBox and ABox axioms : begin
    % TBox axioms with >= or > are essentially enforced on all individuals 
    :- concept_inclusion(C,D,Operator,Alpha), Operator = ">=", @lt(0,max_value, Alpha) = 1; 
        eval(impl(C,D),X,V), @ge(V,max_value, Alpha) != 1.
    :- concept_inclusion(C,D,Operator,Alpha), Operator = ">"; 
        eval(impl(C,D),X,V), @gt(V,max_value, Alpha) != 1.
        
    % TBox axioms with <= and < are associated with their own individuals, and enforced on them
    individual(anonymous(concept_inclusion(C,D,Operator,Alpha))) :- 
        concept_inclusion(C,D,Operator,Alpha), Operator = "<=", @gt(max_value,max_value, Alpha) = 1. 
    individual(anonymous(concept_inclusion(C,D,Operator,Alpha))) :- 
        concept_inclusion(C,D,Operator,Alpha), Operator = "<". 
    :- concept_inclusion(C,D,Operator,Alpha), Operator = "<="; X = concept_inclusion(C,D,Operator,Alpha);
        eval(impl(C,D),X,V), @le(V,max_value, Alpha) != 1.
    :- concept_inclusion(C,D,Operator,Alpha), Operator = "<"; X = concept_inclusion(C,D,Operator,Alpha);
        eval(impl(C,D),X,V), @lt(V,max_value, Alpha) != 1.
        
    % TBox axioms with = are syntactic sugar for <= AND >=
    concept_inclusion(C,D,">=",Alpha) :- concept_inclusion(C,D,Operator,Alpha), Operator = "=".
    concept_inclusion(C,D,"<=",Alpha) :- concept_inclusion(C,D,Operator,Alpha), Operator = "=".
    
    % TBox axioms with != are syntactic sugar for < OR >
    individual(anonymous(concept_inclusion(C,D,Operator,Alpha))) :- 
        concept_inclusion(C,D,Operator,Alpha), Operator = "!=".
    :- concept_inclusion(C,D,Operator,Alpha), Operator = "!="; X = individual(concept_inclusion(C,D,Operator,Alpha));
        eval(impl(C,D),X,V), @lt(V,max_value, Alpha) != 1;
        eval(impl(C,D),_,V'), @gt(V',max_value, Alpha) != 1.
    
    % ABox axioms are applied to specific concepts and individuals, so we just enforce the required condition
    :- assertion(C,X,Operator,Alpha); eval(C,X,V), @apply_operator(V,max_value, Operator,Alpha) != 1.
% TBox and ABox axioms : end

% support exactly-one constraints encoded as 
%   exactly_one(ID). exactly_one_element(ID,Concept). ... exactly_one_element(ID,Concept).
:- exactly_one(ID), individual(X), #count{Concept : exactly_one_element(ID,Concept), eval(Concept,X,max_value)} != 1.

% query witness : begin
    % typical C-elements are those with the highest truth degree
    typical_element(C,X) :- query(C,_,_,_), eval(C,X,V), V = #max{V' : eval(C,X',V')}.
    
    % if the query is >= or >, search for a counterexample falsifying the query
    witness :- query(C,D,Operator,Alpha), Operator = ">=";
       typical_element(C,X), eval(impl(C,D),X,V), @ge(V,max_value, Alpha) != 1.
    witness :- query(C,D,Operator,Alpha), Operator = ">";
       typical_element(C,X), eval(impl(C,D),X,V), @gt(V,max_value, Alpha) != 1.
    
    % if the query is <= or <, search for a counterexample making the query true
    witness :- query(C,D,Operator,Alpha), Operator = "<=";
       typical_element(C,X), eval(impl(C,D),X,V), @le(V,max_value, Alpha) = 1.
    witness :- query(C,D,Operator,Alpha), Operator = "<";
       typical_element(C,X), eval(impl(C,D),X,V), @lt(V,max_value, Alpha) = 1.
           
    :~ witness. [-1@1] 
% query witness : end


#show.
#show eval(C,X,V) : eval(C,X,V), concept(C), @is_named_concept(C) = 1.
#show typical(V) : typical_element(C,X), eval(C,X,V).
#show witness/0.



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

% C=V <=> C>=V and C<V+1
:- concept(C), individual(X); eval(C,X,V), V > 0; not eval_ge(C,X,V).
:- concept(C), individual(X); eval(C,X,V); eval_ge(C,X,V+1).
:- concept(C), individual(X); eval_ge(C,X,V), not eval_ge(C,X,V+1); not eval(C,X,V).

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
:- concept(impl(A,B)), individual(X); 
   eval_ge(impl(A,B),X,V); premise_greater_than_conclusion(A,B,X); not eval_ge(B,X,V).
:- concept(impl(A,B)), individual(X), truth_degree(V), V > 0; 
   not premise_greater_than_conclusion(A,B,X); not eval_ge(impl(A,B),X,V).
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
