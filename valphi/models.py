import dataclasses
from dataclasses import InitVar
from typing import List, Iterable, Any, Tuple

import clingo
import typeguard
from dumbo_asp.utils import validate


@typeguard.typechecked
@dataclasses.dataclass(order=True, unsafe_hash=True, frozen=True)
class Model:
    __value: List[clingo.Symbol]
    key: InitVar[Any] = dataclasses.field()

    __key = object

    def __post_init__(self, key: Any):
        validate("key", key, equals=self.__key)
        self.__value.sort()

    @staticmethod
    def of(model: clingo.Model) -> 'Model':
        return Model([x for x in model.symbols(shown=True)], key=Model.__key)

    @staticmethod
    def empty() -> 'Model':
        return Model([], key=Model.__key)

    @staticmethod
    def of_program(program: Iterable[str]) -> 'Model':
        control = clingo.Control()
        control.add("base", [], '\n'.join(program))
        control.ground([("base", [])])
        model_collect = ModelCollect()
        control.solve(on_model=model_collect)
        validate("one model", model_collect, length=1)
        return model_collect[0]

    def __str__(self):
        return ' '.join(str(x) for x in self.__value)

    def __len__(self):
        return len(self.__value)

    def __getitem__(self, item):
        return self.__value[item]

    def __iter__(self):
        return self.__value.__iter__()

    @property
    def as_strings(self) -> Tuple[str, ...]:
        return tuple(f"{atom}." for atom in self.__value)


@typeguard.typechecked
@dataclasses.dataclass(order=True, unsafe_hash=True, frozen=True)
class ModelList:
    __value: List[Model]

    @staticmethod
    def of(models: Iterable[Model]):
        return ModelList(list(models))

    @staticmethod
    def empty():
        return ModelList([])

    def __post_init__(self):
        self.__value.sort()

    def __str__(self):
        return '-' if self.empty() else '\n'.join(str(x) for x in self.__value)

    def __len__(self):
        return len(self.__value)

    def __getitem__(self, item):
        return self.__value[item]

    def __iter__(self):
        return iter(self.__value)

    def is_emtpy(self):
        return len(self.__value) == 0


@typeguard.typechecked
@dataclasses.dataclass(frozen=True)
class ModelCollect:
    __value: List[Model] = dataclasses.field(default_factory=list)

    def __call__(self, model):
        self.__value.append(Model.of(model))

    def __str__(self):
        return '\n'.join(str(x) for x in self.__value)

    def __len__(self):
        return len(self.__value)

    def __getitem__(self, item):
        return self.__value[item]

    def __iter__(self):
        return iter(self.__value)


@typeguard.typechecked
@dataclasses.dataclass(frozen=True)
class LastModel:
    __value: List[Model] = dataclasses.field(default_factory=list)

    def __call__(self, model):
        self.__value.clear()
        self.__value.append(Model.of(model))

    def __str__(self):
        return str(self.get()) if self.has() else 'NO SOLUTIONS'

    def get(self):
        validate('has', self.has(), equals=True)
        return self.__value[0]

    def has(self):
        return len(self.__value) > 0
