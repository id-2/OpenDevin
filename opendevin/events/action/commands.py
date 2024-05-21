from dataclasses import dataclass, fields
from typing import ClassVar

from opendevin.core.schema import ActionType

from .action import Action


@dataclass
class CmdRunAction(Action):
    command: str
    background: bool = False
    thought: str = ''
    action: str = ActionType.RUN
    runnable: ClassVar[bool] = True

    @property
    def message(self) -> str:
        return f'Running command: {self.command}'

    def __str__(self) -> str:
        ret = '**CmdRunAction**\n'
        if self.thought:
            ret += f'THOUGHT:{self.thought}\n'
        ret += f'COMMAND:\n{self.command}'
        return ret


@dataclass
class CmdKillAction(Action):
    command_id: int
    thought: str = ''
    action: str = ActionType.KILL
    runnable: ClassVar[bool] = True

    @property
    def message(self) -> str:
        return f'Killing command: {self.command_id}'

    def __str__(self) -> str:
        return f'**CmdKillAction**\n{self.command_id}'

    def __eq__(self, other: object) -> bool:
        if Action.is_ignoring_command_id():
            return all(
                getattr(self, f.name) == getattr(other, f.name)
                for f in fields(self)
                if f.name != 'command_id'
            )
        return super().__eq__(other)


@dataclass
class IPythonRunCellAction(Action):
    code: str
    thought: str = ''
    action: str = ActionType.RUN_IPYTHON
    runnable: ClassVar[bool] = True

    def __str__(self) -> str:
        ret = '**IPythonRunCellAction**\n'
        if self.thought:
            ret += f'THOUGHT:{self.thought}\n'
        ret += f'CODE:\n{self.code}'
        return ret

    @property
    def message(self) -> str:
        return f'Running Python code interactively: {self.code}'
