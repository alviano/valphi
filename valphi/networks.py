import dataclasses
from typing import List, Tuple, Optional, Union, Any, Set

import clingo
import typeguard

from valphi import utils
from valphi.models import ModelCollect, Model
from valphi.utils import validate


@typeguard.typechecked
@dataclasses.dataclass(frozen=True)
class NetworkTopology:
    __layers: List[List[List[float]]] = dataclasses.field(default_factory=list, init=False)
    __exactly_one: List[List[int]] = dataclasses.field(default_factory=list, init=False)

    @staticmethod
    def parse(s: Union[str, List[str]]) -> 'NetworkTopology':
        if type(s) == str:
            lines = [x.strip() for x in s.strip().split('\n')]
        else:
            lines = [x.strip() for x in s]
        res = NetworkTopology().add_layer()
        for line in lines:
            if not line:
                continue
            if line == '#':
                res.add_layer()
                continue
            if line.startswith("=1 "):
                res.add_exactly_one([int(x) for x in line.split()[1:]])
                continue
            weights = [float(x) for x in line.split()]
            if res.number_of_layers() == 1:
                for _ in weights[1:]:
                    res.add_node()
                res.add_layer()
            res.add_node(weights)
        return res

    def add_layer(self) -> 'NetworkTopology':
        self.__layers.append([])
        return self

    def add_node(self, weights: Optional[List[float]] = None) -> 'NetworkTopology':
        utils.validate("has layer", self.__layers, min_len=1)
        if len(self.__layers) == 1:
            utils.validate("weights", weights, enforce_not_none=False, equals=None)
            self.__layers[-1].append([])
        else:
            utils.validate("weights", weights, length=1 + len(self.__layers[-2]))
            self.__layers[-1].append(weights)
        return self

    def add_exactly_one(self, input_nodes: List[int]) -> 'NetworkTopology':
        utils.validate("has layer", self.__layers, min_len=1)
        weights = self.__get_layer(1)
        utils.validate("has nodes", all(1 <= node <= len(weights) for node in input_nodes), equals=True)
        self.__exactly_one.append(input_nodes)
        return self

    def __validate_layer_index(self, index) -> None:
        utils.validate("index", index, min_value=1, max_value=len(self.__layers))

    def __get_layer(self, index) -> List[List[float]]:
        self.__validate_layer_index(index)
        return self.__layers[index - 1]

    def number_of_layers(self) -> int:
        return len(self.__layers)

    def number_of_nodes(self, layer: int) -> int:
        weights = self.__get_layer(layer)
        return len(weights)

    def in_weights(self, layer: int, node: int) -> List[float]:
        weights = self.__get_layer(layer)
        utils.validate("node", node, min_value=1, max_value=len(weights))
        return weights[node - 1]

    def number_of_exactly_one(self) -> int:
        return len(self.__exactly_one)

    def nodes_in_exactly_one(self, index: int) -> List[int]:
        utils.validate("index", index, min_value=0, max_value=len(self.__exactly_one) - 1)
        return list(self.__exactly_one[index])

    @staticmethod
    def term(layer: int, node: int) -> str:
        return f"{NetworkTopology.layer_term(layer)}_{node}"

    @staticmethod
    def layer_term(layer: int) -> str:
        return f"l{layer}"


@typeguard.typechecked
@dataclasses.dataclass(frozen=True)
class ArgumentationGraph:
    __attacks: Set[Tuple[Any, Any, float]] = dataclasses.field(default_factory=set, init=False)

    @staticmethod
    def parse(s: Union[str, List[str]]) -> Optional['ArgumentationGraph']:
        if type(s) == str:
            lines = [x.strip() for x in s.strip().split('\n')]
        else:
            lines = [x.strip() for x in s]
        res = ArgumentationGraph()
        state = "init"
        for line in lines:
            if not line:
                continue
            if state == "init":
                if line != "#graph":
                    return None
                state = "attacks"
                continue
            if state == "attacks":
                attacker, attacked, weight = line.split()
                res.add_attack(int(attacker), int(attacked), float(weight))
        return res

    def add_attack(self, attacker: int, attacked: int, weight: float):
        self.__attacks.add((attacker, attacked, weight))

    def __iter__(self):
        return iter(self.__attacks)

    # def compute_attacks_received_by_each_argument(self) -> Dict[Any, List[Tuple[Any, float]]]:
    #     res = defaultdict(list)
    #     for (attacker, attacked, weight) in self:
    #         res[attacked].append((attacker, weight))
    #     return res

    def compute_attacked(self) -> Set[Any]:
        return set(attacked for (attacker, attacked, weight) in self)

    def compute_arguments(self) -> Set[Any]:
        return set(attacker for (attacker, attacked, weight) in self).union(self.compute_attacked())

    @staticmethod
    def term(node: int) -> str:
        return f"a{node}"


@typeguard.typechecked
@dataclasses.dataclass(frozen=True)
class NetworkAspEncoding:
    value: str


@typeguard.typechecked
@dataclasses.dataclass(frozen=True)
class MaxSAT:
    __clauses: List[Tuple[int]] = dataclasses.field(default_factory=list, init=False)

    @staticmethod
    def parse(s: Union[str, List[str]]) -> Optional['MaxSAT']:
        if type(s) == str:
            lines = [x.strip() for x in s.strip().split('\n')]
        else:
            lines = [x.strip() for x in s]
        res = MaxSAT()
        state = "init"
        for line in lines:
            if not line:
                continue
            if state == "init":
                if line.startswith("c"):
                    continue
                if not line.startswith("p cnf "):
                    return None
                state = "clauses"
                continue
            if state == "clauses":
                literals = [int(x) for x in line.split()]
                validate("terminated by 0", literals[-1] == 0)
                literals = literals[:-1]
                res.add_clause(*literals)
        return res

    def __len__(self):
        return len(self.__clauses)

    def __iter__(self):
        return self.__clauses.__iter__()

    def add_clause(self, *literals: int):
        validate("cannot contain zero", any(x == 0 for x in literals), equals=False)
        self.__clauses.append(literals)

    def serialize_clauses_as_facts(self) -> List[str]:
        res = []
        for index, clause in enumerate(self.__clauses, start=1):
            res.append(f"clause(c({index})).")
            for literal in clause:
                if literal > 0:
                    res.append(f"clause_positive_literal(c({index}), x{literal}).")
                else:
                    res.append(f"clause_negative_literal(c({index}), x{-literal}).")
        return res

    def compute_network_facts(self) -> Model:
        control = clingo.Control()
        control.add("base", ["max_value"], '\n'.join(self.serialize_clauses_as_facts()) + """
atom(Atom) :- clause_positive_literal(Clause, Atom).
atom(Atom) :- clause_negative_literal(Clause, Atom).

% boolean assignment
sub_type(A,A, max_value + 1) :- atom(A).

% clause satisfaction
sub_type(C,bias(C),NegativeLiterals * max_value) :- clause(C), NegativeLiterals = #count{A : clause_negative_literal(C,A)}.
sub_type(C,A,max_value) :- clause(C), clause_positive_literal(C,A).
sub_type(C,A,-max_value) :- clause(C), clause_negative_literal(C,A).

% number of satisfied clauses
sub_type(sat,C,1) :- clause(C).

% even_0 is true
sub_type(even(0), bias(even(0)), max_value).

% even'_{i+1} = valphi(n * (1 - even_i + C_{i+1} - 1)) = max(0, C_{i+1} - even_i)   --- 1 if and only if ~even_i & C_i is true
sub_type(even'(I+1),even(I),-max_value) :- I = 0..max_value-1.
sub_type(even'(I+1),c(I+1),max_value) :- I = 0..max_value-1.

% even''_{i+1} = valphi(n * (even_i + 1 - C_{i+1} - 1)) = max(0, even_i - C_{i+1})  --- 1 if and only even_i & ¬C_i is true
sub_type(even''(I+1),even(I),max_value) :- I = 0..max_value-1.
sub_type(even''(I+1),c(I+1),-max_value) :- I = 0..max_value-1.

% even_{i+1} = valphi(n * (even'_{i+1} + even''_{i+1})) = min(1, even'_{i+1} + even''_{i+1})    --- 1 if and only even'_{i+1} | even''_{i+1} is true
sub_type(even(I+1),even'(I+1),max_value) :- I = 0..max_value-1.
sub_type(even(I+1),even''(I+1),max_value) :- I = 0..max_value-1.

#show.
#show sub_type/3.
        """)
        control.ground([("base", [clingo.Number(len(self))])])
        model_collect = ModelCollect()
        control.solve(on_model=model_collect)
        validate("one model", model_collect, length=1)
        return model_collect[0]

    @staticmethod
    def compute_query() -> str:
        return "sat#even(max_value)#1.0"

    def compute_val_phi(self):
        return [truth_degree * len(self) for truth_degree in range(len(self))]
