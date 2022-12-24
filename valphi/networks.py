import dataclasses
from typing import List, Tuple, Optional, Union, Any, Set, FrozenSet

import clingo
import typeguard
from distlib.util import cached_property

from valphi import utils
from valphi.models import ModelCollect, Model
from valphi.propagators import ValPhiPropagator


@typeguard.typechecked
@dataclasses.dataclass(frozen=True)
class NetworkInterface:
    __complete: List[bool] = dataclasses.field(default_factory=lambda: [False], init=False)

    __parse_key = object()

    @staticmethod
    def parse(s: Union[str, List[str]]) -> 'NetworkInterface':
        if type(s) == str:
            lines = [x.strip() for x in s.strip().split('\n')]
        else:
            lines = [x.strip() for x in s]
        res = MaxSAT.parse_implementation(lines, NetworkInterface.__parse_key)
        if res is None:
            res = ArgumentationGraph.parse_implementation(lines, NetworkInterface.__parse_key)
        if res is None:
            res = NetworkTopology.parse_implementation(lines, NetworkInterface.__parse_key)
        return res

    def complete(self):
        utils.validate("complete", self.__complete[0], equals=False)
        self.__complete[0] = True
        return self

    @staticmethod
    def validate_parse_key(key: Any):
        utils.validate("key", key, equals=NetworkInterface.__parse_key)

    def validate_is_complete(self):
        utils.validate("complete", self.__complete[0], equals=True)

    def validate_is_not_complete(self):
        utils.validate("not complete", self.__complete[0], equals=False)

    @cached_property
    def network_facts(self) -> Model:
        self.validate_is_complete()
        return self._network_facts

    @cached_property
    def _network_facts(self) -> Model:
        raise NotImplemented

    def register_propagators(self, control: clingo.Control, val_phi: List[float]) -> None:
        self.validate_is_complete()
        return self._register_propagators(control, val_phi)

    def _register_propagators(self, control: clingo.Control, val_phi: List[float]) -> None:
        raise NotImplemented

    @cached_property
    def val_phi(self):
        raise NotImplemented


@typeguard.typechecked
@dataclasses.dataclass(frozen=True)
class NetworkTopology(NetworkInterface):
    __layers: List[List[List[float]]] = dataclasses.field(default_factory=list, init=False)
    __exactly_one: List[List[int]] = dataclasses.field(default_factory=list, init=False)

    @staticmethod
    def parse_implementation(lines: List[str], key: Any) -> 'NetworkTopology':
        NetworkInterface.validate_parse_key(key)
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
            if len(res.__layers) == 1:
                for _ in weights[1:]:
                    res.add_node()
                res.add_layer()
            res.add_node(weights)
        return res.complete()

    def add_layer(self) -> 'NetworkTopology':
        self.validate_is_not_complete()
        self.__layers.append([])
        return self

    def add_node(self, weights: Optional[List[float]] = None) -> 'NetworkTopology':
        self.validate_is_not_complete()
        utils.validate("has layer", self.__layers, min_len=1)
        if len(self.__layers) == 1:
            utils.validate("weights", weights, enforce_not_none=False, equals=None)
            self.__layers[-1].append([])
        else:
            utils.validate("weights", weights, length=1 + len(self.__layers[-2]))
            self.__layers[-1].append(weights)
        return self

    def add_exactly_one(self, input_nodes: List[int]) -> 'NetworkTopology':
        self.validate_is_not_complete()
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
        self.validate_is_complete()
        return len(self.__layers)

    def number_of_nodes(self, layer: int) -> int:
        self.validate_is_complete()
        weights = self.__get_layer(layer)
        return len(weights)

    def in_weights(self, layer: int, node: int) -> List[float]:
        self.validate_is_complete()
        weights = self.__get_layer(layer)
        utils.validate("node", node, min_value=1, max_value=len(weights))
        return weights[node - 1]

    def number_of_exactly_one(self) -> int:
        self.validate_is_complete()
        return len(self.__exactly_one)

    def nodes_in_exactly_one(self, index: int) -> List[int]:
        self.validate_is_complete()
        utils.validate("index", index, min_value=0, max_value=len(self.__exactly_one) - 1)
        return list(self.__exactly_one[index])

    @staticmethod
    def term(layer: int, node: int) -> str:
        return f"{NetworkTopology.layer_term(layer)}_{node}"

    @staticmethod
    def layer_term(layer: int) -> str:
        return f"l{layer}"

    @cached_property
    def _network_facts(self) -> Model:
        res = ["binary_input."]
        for layer_index, _ in enumerate(range(self.number_of_layers()), start=1):
            for node_index, _ in enumerate(range(self.number_of_nodes(layer=layer_index)), start=1):
                weights = self.in_weights(layer=layer_index, node=node_index)
                if weights:
                    res.append(f"sub_type({self.term(layer_index, node_index)},"
                               f"top,\"{weights[0]}\").")
                    for weight_index, weight in enumerate(weights[1:], start=1):
                        res.append(
                            f"sub_type({self.term(layer_index, node_index)},"
                            f"{self.term(layer_index - 1, weight_index)},\"{weight}\").")
        for index in range(self.number_of_exactly_one()):
            nodes = self.nodes_in_exactly_one(index)
            res.append(f"exactly_one({index}).")
            for node in nodes:
                res.append(f"exactly_one({index},{self.term(1, node)}).")
        return Model.of_program(res)

    def _register_propagators(self, control: clingo.Control, val_phi: List[float]) -> None:
        for layer_index, _ in enumerate(range(1, self.number_of_layers()), start=2):
            for node_index, _ in enumerate(range(self.number_of_nodes(layer=layer_index)), start=1):
                propagator = ValPhiPropagator(self.term(layer_index, node_index), val_phi=val_phi)
                control.register_propagator(propagator)


@typeguard.typechecked
@dataclasses.dataclass(frozen=True)
class ArgumentationGraph(NetworkInterface):
    __attacks: Set[Tuple[Any, Any, float]] = dataclasses.field(default_factory=set, init=False)

    @staticmethod
    def parse_implementation(lines: List[str], key: Any) -> Optional['ArgumentationGraph']:
        NetworkInterface.validate_parse_key(key)
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
        return res.complete()

    def add_attack(self, attacker: int, attacked: int, weight: float) -> 'ArgumentationGraph':
        self.__attacks.add((attacker, attacked, weight))
        return self

    # def compute_attacks_received_by_each_argument(self) -> Dict[Any, List[Tuple[Any, float]]]:
    #     res = defaultdict(list)
    #     for (attacker, attacked, weight) in self:
    #         res[attacked].append((attacker, weight))
    #     return res

    @cached_property
    def attacked(self) -> FrozenSet[Any]:
        self.validate_is_complete()
        return frozenset(attacked for (attacker, attacked, weight) in self.__attacks)

    @cached_property
    def arguments(self) -> FrozenSet[Any]:
        self.validate_is_complete()
        return frozenset(attacker for (attacker, attacked, weight) in self.__attacks).union(self.attacked)

    @staticmethod
    def term(node: int) -> str:
        return f"a{node}"

    @cached_property
    def _network_facts(self) -> Model:
        return Model.of_program([
            f"attack({self.term(attacker)}, {self.term(attacked)}, \"{weight}\")."
            for (attacker, attacked, weight) in self.__attacks
        ])

    def _register_propagators(self, control: clingo.Control, val_phi: List[float]) -> None:
        for attacked in self.attacked:
            control.register_propagator(ValPhiPropagator(self.term(attacked), val_phi=val_phi))


@typeguard.typechecked
@dataclasses.dataclass(frozen=True)
class MaxSAT(NetworkInterface):
    __clauses: List[Tuple[int]] = dataclasses.field(default_factory=list, init=False)

    @staticmethod
    def parse_implementation(lines: List[str], key: Any) -> Optional['MaxSAT']:
        NetworkInterface.validate_parse_key(key)
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
                utils.validate("terminated by 0", literals[-1] == 0)
                literals = literals[:-1]
                res.add_clause(*literals)
        return res.complete()

    @cached_property
    def number_of_clauses(self):
        self.validate_is_complete()
        return len(self.__clauses)

    def add_clause(self, *literals: int) -> 'MaxSAT':
        self.validate_is_not_complete()
        utils.validate("cannot contain zero", any(x == 0 for x in literals), equals=False)
        self.__clauses.append(literals)
        return self

    def serialize_clauses_as_facts(self) -> List[str]:
        self.validate_is_complete()
        res = []
        for index, clause in enumerate(self.__clauses, start=1):
            res.append(f"clause(c({index})).")
            for literal in clause:
                if literal > 0:
                    res.append(f"clause_positive_literal(c({index}), x{literal}).")
                else:
                    res.append(f"clause_negative_literal(c({index}), x{-literal}).")
        return res

    @cached_property
    def _network_facts(self) -> Model:
        max_value = clingo.Number(self.number_of_clauses)
        return Model.of_program(self.serialize_clauses_as_facts() + [f"""
atom(Atom) :- clause_positive_literal(Clause, Atom).
atom(Atom) :- clause_negative_literal(Clause, Atom).

% boolean assignment
sub_type(A,A, {max_value} + 1) :- atom(A).

% clause satisfaction
sub_type(C,top,NegativeLiterals * {max_value}) :- clause(C), NegativeLiterals = #count{{A : clause_negative_literal(C,A)}}.
sub_type(C,A,{max_value}) :- clause(C), clause_positive_literal(C,A).
sub_type(C,A,-{max_value}) :- clause(C), clause_negative_literal(C,A).

% number of satisfied clauses
sub_type(sat,C,1) :- clause(C).

% even_0 is true
sub_type(even(0), top, {max_value}).

% even'(i+1) = valphi(n * (1 - even_i + C(i+1) - 1)) = max(0, C(i+1) - even_i)   --- 1 if and only if ~even_i & C_i is true
sub_type(even'(I+1),even(I),-{max_value}) :- I = 0..{max_value}-1.
sub_type(even'(I+1),c(I+1),{max_value}) :- I = 0..{max_value}-1.

% even''(i+1) = valphi(n * (even_i + 1 - C(i+1) - 1)) = max(0, even_i - C(i+1))  --- 1 if and only even_i & ¬C_i is true
sub_type(even''(I+1),even(I),{max_value}) :- I = 0..{max_value}-1.
sub_type(even''(I+1),c(I+1),-{max_value}) :- I = 0..{max_value}-1.

% even(i+1) = valphi(n * (even'(i+1) + even''(i+1))) = min(1, even'(i+1) + even''(i+1))    --- 1 if and only even'(i+1) | even''(i+1) is true
sub_type(even(I+1),even'(I+1),{max_value}) :- I = 0..{max_value}-1.
sub_type(even(I+1),even''(I+1),{max_value}) :- I = 0..{max_value}-1.

#show.
#show sub_type/3.
        """])

    @cached_property
    def query(self) -> str:
        self.validate_is_complete()
        return "sat#even(max_value)#1.0"

    @cached_property
    def val_phi(self):
        self.validate_is_complete()
        return [truth_degree * self.number_of_clauses for truth_degree in range(self.number_of_clauses)]

    def _register_propagators(self, control: clingo.Control, val_phi: List[float]) -> None:
        output_nodes = Model.of_program(self.network_facts.as_strings() + ("""
#show.
#show Node : sub_type(Node,_,_).
        """,))
        for node in output_nodes:
            control.register_propagator(ValPhiPropagator(str(node), val_phi=val_phi))
