import re
from pathlib import Path
from typing import Callable, Final

import valid8
from rich.console import Console
from rich.prompt import Prompt, Confirm
from typeguard import typechecked

PROJECT_ROOT: Final = Path(__file__).parent.parent

console = Console()
prompt = Prompt(console=console)
confirm = Confirm(console=console)


@typechecked
def pattern(regex: str) -> Callable[[str], bool]:
    r = re.compile(regex)

    def res(value):
        return bool(r.fullmatch(value))

    res.__name__ = f'pattern({regex})'
    return res


validate = valid8.validate
ValidationError = valid8.ValidationError
