import dataclasses
from typing import List, Iterable

import typeguard
from dumbo_asp.primitives.models import Model
from dumbo_utils.validation import validate


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
        self.__value.append(Model.of_elements(model.symbols(shown=True)))

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
        self.__value.append(Model.of_elements(model.symbols(shown=True)))

    def __str__(self):
        return str(self.get()) if self.has() else 'NO SOLUTIONS'

    def get(self):
        validate('has', self.has(), equals=True)
        return self.__value[0]

    def has(self):
        return len(self.__value) > 0
