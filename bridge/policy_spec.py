from dataclasses import dataclass, field
from typing import Any


class BridgeError(Exception):
    pass


@dataclass(frozen=True)
class TypeSpec:
    name: str


NatType = TypeSpec("Nat")
StringType = TypeSpec("String")
BoolType = TypeSpec("Bool")


@dataclass(frozen=True)
class FinsetType:
    elem_type: TypeSpec


@dataclass(frozen=True)
class FunctionDef:
    name: str
    arg_type: TypeSpec
    return_type: TypeSpec
    mapping: dict[str, Any]
    default: Any = 0


@dataclass(frozen=True)
class PolicySpec:
    name: str
    params: dict[str, TypeSpec]
    functions: list[FunctionDef] = field(default_factory=list)
    violation_expr: str = ""
    description: str = ""
