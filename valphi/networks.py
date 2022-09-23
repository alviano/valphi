import dataclasses
from typing import List, Tuple, Optional, Union

from valphi import utils


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
