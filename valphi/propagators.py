from typing import Optional, List

import clingo
from clingo.propagator import Propagator
from dumbo_utils.validation import validate


class ValPhiPropagator(Propagator):
    def __init__(self, output_node: str, val_phi: List[float]):
        super().__init__()
        self.output_node = output_node
        self.val_phi = list(val_phi)
        self.max_value = len(self.val_phi)
        self.trail = []
        self.input_nodes = set()
        self.input_node_lit_to_value = {}
        self.input_value = {}
        self.input_weight = {}
        self.output_node_lit_to_value = {}
        self.output_value_to_node_lit = {}
        self.output_value = None

    def __reset(self):
        self.trail.clear()
        self.input_nodes.clear()
        self.input_node_lit_to_value.clear()
        self.input_value.clear()
        self.input_weight.clear()
        self.output_node_lit_to_value.clear()
        self.output_value_to_node_lit.clear()
        self.output_value = None

    def __validate_max_value(self, init) -> None:
        max_value = max(s.symbol.arguments[0].number for s in init.symbolic_atoms.by_signature("truth_degree", 1))
        validate("max_value", max_value, equals=self.max_value,
                 help_msg="The provided ValPhi doesn't match the number of truth values")

    def __read_input_nodes(self, init) -> None:
        for s in init.symbolic_atoms.by_signature("weighted_typicality_inclusion", 3):
            concept1, concept2, weight = s.symbol.arguments
            if str(concept1) == self.output_node:
                self.input_nodes.add(concept2)
                self.input_value[concept2] = None
                self.input_weight[concept2] = float(weight.string) if weight.type == clingo.SymbolType.String \
                    else float(weight.number)

    def __read_eval(self, init) -> None:
        for s in init.symbolic_atoms.by_signature("eval", 3):
            concept, individual, value = s.symbol.arguments
            validate("empty ABox", individual, equals=clingo.Function("anonymous"),
                     help_msg="Propagator requires empty ABox")
            lit = init.solver_literal(s.literal)
            if self.__is_false(lit):
                continue
            if str(concept) == self.output_node:
                if self.__is_true(lit):
                    self.output_value = value.number
                else:
                    assert lit not in self.output_node_lit_to_value
                    self.output_node_lit_to_value[lit] = value.number
                    self.output_value_to_node_lit[value.number] = lit
                    init.add_watch(lit)
            if concept in self.input_nodes:
                if self.__is_true(lit):
                    self.input_value[concept] = value.number
                else:
                    assert lit not in self.input_node_lit_to_value
                    self.input_node_lit_to_value[lit] = (concept, value.number)
                    init.add_watch(lit)

    def init(self, init):
        self.__reset()
        self.__validate_max_value(init)
        self.__read_input_nodes(init)
        self.__read_eval(init)

    def propagate(self, ctl, changes):
        for lit in changes:
            self.trail.append(lit)
            if lit in self.output_node_lit_to_value:
                self.output_value = self.output_node_lit_to_value[lit]
            if lit in self.input_node_lit_to_value:
                concept, value = self.input_node_lit_to_value[lit]
                self.input_value[concept] = value

        output_value = self.__compute_output_value()
        if output_value is None:
            return
        if self.output_value is None:
            if output_value in self.output_value_to_node_lit:
                unit = self.output_value_to_node_lit[output_value]
                if ctl.add_clause([-lit for lit in self.trail] + [unit]):
                    ctl.propagate()
            else:
                ctl.add_clause([-lit for lit in self.trail])
            return
        if output_value != self.output_value:
            ctl.add_clause([-lit for lit in self.trail])

    def undo(self, thread_id, assignment, changes):
        for lit in reversed(changes):
            assert lit == self.trail[-1]
            self.trail.pop()
            if lit in self.output_node_lit_to_value:
                self.output_value = None
                continue
            assert lit in self.input_node_lit_to_value
            concept, value = self.input_node_lit_to_value[lit]
            self.input_value[concept] = None

    def __compute_output_value(self) -> Optional[int]:
        if any(x is None for x in self.input_value.values()):
            return None

        weight = sum(self.input_value[node] * self.input_weight[node] for node in self.input_nodes)
        actual = self.max_value
        for index, value in enumerate(self.val_phi):
            if weight <= value:
                actual = index
                break
        return actual

    def print_state(self):
        print(f"ValPhi-propagator for {self.output_node}")
        for node in self.input_nodes:
            print(f"  {node} = {self.input_value[node]}  [{self.input_weight[node]}]")
        weight_value = self.__compute_output_value()
        print(f"  {self.output_node} = {self.output_value}")
        if weight_value:
            print(f"  valphi = {weight_value}")

    @staticmethod
    def __is_false(lit: int) -> bool:
        return lit == -1

    @staticmethod
    def __is_true(lit: int) -> bool:
        return lit == 1
