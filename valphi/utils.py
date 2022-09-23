import dataclasses
import re
from typing import Callable, List, Iterable

import clingo
import typeguard
import valid8
from dataclass_type_validator import dataclass_type_validator, TypeValidationError
from typeguard import typechecked

from rich.console import Console
from rich.prompt import Prompt, Confirm

console = Console()
prompt = Prompt(console=console)
confirm = Confirm(console=console)


def validate_dataclass(data):
    try:
        dataclass_type_validator(data)
    except TypeValidationError as e:
        raise TypeError(e)


@typechecked
def pattern(regex: str) -> Callable[[str], bool]:
    r = re.compile(regex)

    def res(value):
        return bool(r.fullmatch(value))

    res.__name__ = f'pattern({regex})'
    return res


validate = valid8.validate
ValidationError = valid8.ValidationError
