from dataclasses import dataclass, field


class ValidationError(Exception):
    def __init__(self, message: str, field: str | None = None):
        self.field = field
        super().__init__(message)


@dataclass
class ParamSpec:
    name: str
    type: str
    enum: list[str] | None = None
    required: bool = True


@dataclass
class ToolSchema:
    tool_name: str
    params: list[ParamSpec] = field(default_factory=list)

    def validate(self, args: dict) -> dict:
        validated = {}

        for param in self.params:
            raw = args.get(param.name)

            if param.required and raw is None:
                raise ValidationError(
                    f"Missing required parameter '{param.name}'",
                    field=param.name,
                )

            if raw is None:
                continue

            validated[param.name] = self._coerce(param, raw)

        return validated

    @staticmethod
    def _coerce(param: ParamSpec, raw) -> str | int | bool:
        if param.type == "int":
            if isinstance(raw, str):
                try:
                    return int(raw)
                except ValueError:
                    try:
                        return int(float(raw))
                    except ValueError:
                        raise ValidationError(
                            f"Cannot coerce '{raw}' to int for '{param.name}'",
                            field=param.name,
                        )
            if isinstance(raw, int):
                if param.enum:
                    str_val = str(raw)
                    if str_val not in param.enum:
                        allowed = ", ".join(param.enum)
                        raise ValidationError(
                            f"Value '{raw}' for '{param.name}' is not valid. "
                            f"Allowed: {allowed}",
                            field=param.name,
                        )
                return raw
            raise ValidationError(
                f"Expected int for '{param.name}', got {type(raw).__name__}",
                field=param.name,
            )

        if param.type == "string":
            val = str(raw)
            if param.enum:
                if val not in param.enum:
                    allowed = ", ".join(param.enum)
                    raise ValidationError(
                        f"Value '{val}' for '{param.name}' is not valid. "
                        f"Allowed: {allowed}",
                        field=param.name,
                    )
            return val

        if param.type == "bool":
            if isinstance(raw, bool):
                return raw
            if isinstance(raw, str):
                return raw.lower() in ("true", "1", "yes")
            if isinstance(raw, int):
                return bool(raw)
            raise ValidationError(
                f"Expected bool for '{param.name}', got {type(raw).__name__}",
                field=param.name,
            )

        return str(raw)


SCHEMAS: dict[str, ToolSchema] = {
    "confirm_sale": ToolSchema(
        tool_name="confirm_sale",
        params=[
            ParamSpec(name="model", type="string", enum=["Tahoe", "Malibu"]),
            ParamSpec(name="price", type="int"),
            ParamSpec(name="customer", type="string", required=False),
        ],
    ),
    "delete_file": ToolSchema(
        tool_name="delete_file",
        params=[
            ParamSpec(name="target", type="string"),
        ],
    ),
}


def validate_tool_call(tool: str, args: dict) -> dict:
    schema = SCHEMAS.get(tool)
    if schema is None:
        raise ValidationError(f"No schema registered for tool '{tool}'")
    return schema.validate(args)
