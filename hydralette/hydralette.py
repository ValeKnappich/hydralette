import builtins
import inspect
import sys
from collections.abc import Mapping
from typing import Any, Callable, Union

import yaml


class UNSPECIFIED_TYPE:
    def __repr__(self):
        return self.__class__.__name__


UNSPECIFIED = UNSPECIFIED_TYPE()


class MissingArgumentError(Exception):
    pass


class MisconfigurationError(Exception):
    pass


class ValidationError(Exception):
    pass


class OverrideError(Exception):
    pass


def is_builtin(v: Any) -> bool:
    return v in vars(builtins).values()


def fields_from_signature(signature: inspect.Signature) -> dict:
    return {param.name: Field.from_signature_paramter(param) for param in signature.parameters.values()}


class Config:
    def __init__(
        self,
        _validate: Callable[[Any], Any] | UNSPECIFIED_TYPE = UNSPECIFIED,
        _groups: dict[str, Union["Config", Any]] | UNSPECIFIED_TYPE = UNSPECIFIED,
        _from_signature: Callable | UNSPECIFIED_TYPE = UNSPECIFIED,
        **_fields,
    ):
        self._validate = _validate
        self._groups = _groups
        self._from_signature = _from_signature
        self._fields = self._make_fields(_fields)

        n_methods = sum(
            (
                not isinstance(self._groups, UNSPECIFIED_TYPE),
                not isinstance(self._from_signature, UNSPECIFIED_TYPE),
                len(self._fields) > 0,
            )
        )
        if n_methods > 1:
            raise MisconfigurationError("Can only specify one of (_groups, _from_signature, fields)")

        self._current_group = UNSPECIFIED
        if not isinstance(self._groups, UNSPECIFIED_TYPE):
            if "_default" not in self._groups:
                raise MisconfigurationError("'_default' must be in _groups dict")
            self._current_group = self._groups.pop("_default")
            for key, group in self._groups.items():
                if not isinstance(group, Config):
                    raise MisconfigurationError(f"group value for '{key}'must be a Config")

        if not isinstance(self._from_signature, UNSPECIFIED_TYPE):
            self._fields = fields_from_signature(inspect.signature(self._from_signature))

    def _make_fields(self, fields: dict[str, Any]) -> dict[str, "Config | Field"]:
        for k, v in fields.items():
            if not isinstance(v, Field) and not isinstance(v, Config):
                fields[k] = Field(default=v)
        return fields

    def check_required_args(self, _path="") -> None:
        for name, field in self._fields.items():
            if isinstance(field, Field):
                if isinstance(field.value, UNSPECIFIED_TYPE):
                    raise MissingArgumentError(f"Required argument '{_path}{name}' is missing")
                if not isinstance(field.validate, UNSPECIFIED_TYPE) and not field.validate():  # type: ignore
                    raise ValidationError(f"Field validation failed on '{_path}.{name}' for {field.value}")

            elif isinstance(field, Config):
                field.check_required_args(_path=f"{_path}{name}.")

    def apply(self, overrides: list[str] | dict = sys.argv[1:]) -> None:
        self.override(overrides)
        self.resolve_references()
        self.validate()
        self.check_required_args()

    def validate(self, _path="") -> None:
        if not isinstance(self._validate, UNSPECIFIED_TYPE):
            if not self._validate(self):
                raise ValidationError(f"Config validation failed for {self.to_dict()}")

        for name, field in self._fields.items():
            if isinstance(field, Config):
                field.check_required_args(_path=f"{_path}{name}.")

    def override(self, overrides: list[str] | dict = sys.argv[1:]) -> None:
        if isinstance(overrides, list):
            if "--help" in overrides:
                self.print_help()
                sys.exit(0)

            for i in range(0, len(overrides), 2):
                key = overrides[i][2:]
                value = overrides[i + 1]

                if "." in key:
                    first_key = key.split(".")[0]
                    rest = ".".join(key.split(".")[1:])

                    cfg = self if isinstance(self._groups, UNSPECIFIED_TYPE) else self._groups[self._current_group]  # type: ignore
                    if first_key not in cfg._fields:
                        raise OverrideError(f"Override key '{first_key}' not found")
                    sub_cfg = cfg._fields[first_key]
                    if not isinstance(sub_cfg, Config):
                        raise OverrideError(f"Field '{first_key}' is not a Config")
                    sub_cfg.override([f"--{rest}", value])

                else:
                    if isinstance(self._groups, UNSPECIFIED_TYPE):
                        if key not in self._fields:
                            raise OverrideError(f"Override key {key} not found")

                        child = self._fields[key]
                        if isinstance(child, Field):
                            child.value = child.convert_value(value)

                        elif isinstance(child, Config):
                            if isinstance(child._groups, UNSPECIFIED_TYPE):
                                raise OverrideError("Can't override config unless it has groups")
                            elif value not in child._groups:
                                raise OverrideError(f"Group '{value}' does not exist")
                            child._current_group = value
                    else:
                        fields = self._groups[self._current_group]._fields  # type: ignore
                        if key not in fields:
                            raise OverrideError(f"Field '{key}' not found")
                        child = fields[key]
                        if not isinstance(child, Field):
                            raise OverrideError("Can't override config unless it has groups")
                        child.value = child.convert_value(value)

        elif isinstance(overrides, Mapping):
            # def flatten_dict(nested_dict, prefix='--'):
            #     flattened = []
            #     for key, value in nested_dict.items():
            #         if isinstance(value, Mapping):
            #             flattened.extend(flatten_dict(value, prefix + key + '.'))
            #         else:
            #             flattened.append(f'{prefix}{key} {value}')
            #     return flattened

            # self.override(flatten_dict(overrides))

            # converting to string is problematic because values are converted to string --> need to re-implement recursion for mappings
            raise NotImplementedError("Overrides from mapping not supported yet")

    def resolve_references(self, _root: "Config | UNSPECIFIED_TYPE" = UNSPECIFIED) -> None:
        if isinstance(_root, UNSPECIFIED_TYPE):
            _root = self

        if isinstance(self._groups, UNSPECIFIED_TYPE):
            fields = self._fields
        else:
            fields = self._groups[self._current_group]._fields  # type: ignore

        for field in fields.values():
            if isinstance(field, Field) and not isinstance(field.reference, UNSPECIFIED_TYPE):
                field.value = field.reference(self)

            elif isinstance(field, Field) and not isinstance(field.reference_root, UNSPECIFIED_TYPE):
                field.value = field.reference_root(_root)

            elif isinstance(field, Config):
                field.resolve_references(_root=_root)

    def print_help(self, _path: str = "", _group_prefix: str = "", _root: bool = True) -> None:
        if _root:
            print(f"Usage python {sys.argv[0]} [OPTIONS]")

        field_fields = [(field_name, field) for field_name, field in self._fields.items() if isinstance(field, Field)]
        config_fields = [(field_name, field) for field_name, field in self._fields.items() if isinstance(field, Config)]
        groups = (
            [(group_name, group) for group_name, group in self._groups.items()]
            if not isinstance(self._groups, UNSPECIFIED_TYPE)
            else []
        )

        print_space = True

        if _group_prefix:
            print(f"\n{_group_prefix}")
            print_space = False

        for field_name, field in field_fields:
            default = UNSPECIFIED
            if not isinstance(field.default, UNSPECIFIED_TYPE):
                default = field.default
            elif not isinstance(field.default_factory, UNSPECIFIED_TYPE):
                default = field.default_factory()
            help_text = ""
            if not isinstance(field.help, UNSPECIFIED_TYPE):
                help_text = f"\t\t\t{field.help}"

            if print_space:
                print()
                print_space = False
            print(f"--{_path}{field_name} {default}{help_text}")

        for field_name, field in config_fields:
            field.print_help(_path=_path + field_name + ".", _root=False)

        for group_name, group in groups:
            group.print_help(_path, f"if --{_path[:-1]} {group_name}", _root=False)

    @classmethod
    def from_dict(cls, d: dict) -> "Config":
        cfg_dict = {k: v if not isinstance(v, dict) else Config.from_dict(v) for k, v in d.items()}
        return Config(**cfg_dict)  # type: ignore

    def to_dict(self) -> dict:
        def format_value(v):
            if isinstance(v, Field):
                return v.value
            elif isinstance(v, Config):
                return v.to_dict()
            else:
                return v

        if isinstance(self._groups, UNSPECIFIED_TYPE):
            return {k: format_value(v) for k, v in self._fields.items()}
        else:
            group = self._groups[self._current_group]  # type: ignore
            return {k: format_value(v) for k, v in group._fields.items()}

    def to_yaml(self) -> str:
        def normalize_values(d: dict):
            for k, v in d.items():
                if isinstance(v, dict):
                    d[k] = normalize_values(v)
                elif is_builtin(type(v)):
                    d[k] = v
                else:
                    d[k] = repr(v)
            return d

        return yaml.dump(normalize_values(self.to_dict()), sort_keys=False).strip()

    def __repr__(self) -> str:
        return self.to_yaml()

    def __getattr__(self, __name: str) -> Any:
        if __name in self._fields:
            v = self._fields[__name]
            if isinstance(v, Field):
                return v.value
            elif isinstance(v, Config):
                return v
            else:
                raise Exception("field values should only be Field's or Config's?")

        elif not isinstance(self._groups, UNSPECIFIED_TYPE):
            return getattr(self._groups[self._current_group], __name)  # type: ignore

        raise AttributeError(f"{__name} not found. Fields: {list(self._fields.keys())}")

    def __setattr__(self, __name: str, __value: Any) -> None:
        if __name in {
            "_validate",
            "_groups",
            "_from_signature",
            "_current_group",
            "_fields",
        }:
            super().__setattr__(__name, __value)

        elif __name in self._fields:
            orig_value = self._fields[__name].value
            self._fields[__name].value = __value
            if not isinstance(self._validate, UNSPECIFIED_TYPE):
                if not self._validate(self):
                    msg = f"Config validation failed for {self.to_dict()}"
                    self._fields[__name].value = orig_value
                    raise ValidationError(msg)

        elif not isinstance(self._groups, UNSPECIFIED_TYPE):
            setattr(self._groups[self._current_group], __name, __value)  # type: ignore

        else:
            raise AttributeError(f"{__name} not found")


class Field:
    def __init__(
        self,
        type: type | UNSPECIFIED_TYPE = UNSPECIFIED,
        default: Any | UNSPECIFIED_TYPE = UNSPECIFIED,
        default_factory: Callable[[], Any] | UNSPECIFIED_TYPE = UNSPECIFIED,
        convert: Callable[[str], Any] | UNSPECIFIED_TYPE = UNSPECIFIED,
        validate: Callable[[Any], bool] | UNSPECIFIED_TYPE = UNSPECIFIED,
        reference: Callable[[Config], Any] | UNSPECIFIED_TYPE = UNSPECIFIED,
        reference_root: Callable[[Config], Any] | UNSPECIFIED_TYPE = UNSPECIFIED,
        help: str | UNSPECIFIED_TYPE = UNSPECIFIED,
    ):
        self.type = type
        self.default = default
        self.default_factory = default_factory
        self.convert = convert
        self.validate = validate
        self.help = help
        self.reference = reference
        self.reference_root = reference_root

        self._value = None
        _value = UNSPECIFIED
        if not isinstance(default, UNSPECIFIED_TYPE):
            _value = default
        elif not isinstance(default_factory, UNSPECIFIED_TYPE):
            _value = default_factory()
        self.value = _value

        if isinstance(self.type, UNSPECIFIED_TYPE) and not isinstance(self.value, UNSPECIFIED_TYPE):
            self.type = builtins.type(self.value)

    @classmethod
    def from_signature_paramter(cls, parameter: inspect.Parameter) -> "Field":
        kwargs = {}

        if parameter.annotation != inspect._empty:
            kwargs["type"] = parameter.annotation

        if parameter.default != inspect._empty:
            kwargs["default"] = parameter.default
        elif parameter.kind == inspect.Parameter.VAR_KEYWORD:
            kwargs["default"] = {}
        elif parameter.kind == inspect.Parameter.VAR_POSITIONAL:
            kwargs["default"] = []

        if "default" in kwargs and "type" not in kwargs:
            kwargs["type"] = type(kwargs["default"])

        return Field(**kwargs)

    def convert_value(self, value: Any) -> Any:
        if not isinstance(self.convert, UNSPECIFIED_TYPE):
            value = self.convert(value)

        elif not isinstance(self.type, UNSPECIFIED_TYPE) and callable(self.type):
            try:
                value = self.type(value)
            except:  # noqa
                if value == "None":
                    value = None

        return value

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        if not isinstance(self.validate, UNSPECIFIED_TYPE):
            if not self.validate(v):
                raise ValidationError(f"Field validation failed for {v}")
        self._value = v

    def __repr__(self):
        return repr(self.value)
