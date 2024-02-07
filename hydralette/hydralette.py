import builtins
import inspect
import sys
from pathlib import Path
from typing import Any, Callable, Union

import dill
import yaml


class UNSPECIFIED_TYPE:
    def __repr__(self):
        return self.__class__.__name__


UNSPECIFIED = UNSPECIFIED_TYPE()

BOOLEAN_NEGATED_FLAG_PREFIX = "no-"

SPECIAL_VALUES = {"True": True, "False": False, "None": None}


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


def get_all_fields(cfg: "Config"):
    all_fields = {**cfg._fields}
    if (
        not isinstance(cfg._groups, UNSPECIFIED_TYPE)
        and isinstance(cfg._current_group, str)
        and isinstance(cfg._groups[cfg._current_group], Config)
    ):
        all_fields = {**cfg._groups[cfg._current_group]._fields, **all_fields}
    return all_fields


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
        self._current_group = UNSPECIFIED
        self._from_signature = _from_signature
        self._fields = {}

        # 1. initialize fields from signature
        if not isinstance(self._from_signature, UNSPECIFIED_TYPE):
            self._fields = fields_from_signature(inspect.signature(self._from_signature))

        # 2. set fields from kwargs (potentially overriding fields from signature)
        if _fields:
            self._fields = {**self._fields, **self._make_fields(_fields)}

        # 3. validate groups and set _current_group to _default
        if not isinstance(self._groups, UNSPECIFIED_TYPE):
            if "_default" not in self._groups:
                raise MisconfigurationError("'_default' must be in _groups dict")
            self._current_group = self._groups.pop("_default")

    def _make_fields(self, fields: dict[str, Any]) -> dict[str, "Config | Field"]:
        """Create Field objects for fields that were passed as default value only."""
        for k, v in fields.items():
            if not isinstance(v, Field) and not isinstance(v, Config):
                fields[k] = Field(default=v)
        return fields

    def check_required_args(self, _path="") -> None:
        """Verify that all required arguments were set. Recursively searches config fields for UNSPECIFIED"""
        for name, field in get_all_fields(self).items():
            if isinstance(field, Field):
                if isinstance(field.value, UNSPECIFIED_TYPE):
                    raise MissingArgumentError(f"Required argument '{_path}{name}' is missing")

            elif isinstance(field, Config):
                field.check_required_args(_path=f"{_path}{name}.")

    def apply(self, overrides: list[str] = sys.argv[1:]) -> None:
        """Convenience method for common workflow after instantiation.
        Overrides fields from CLI, resolves references, searches for unset required arguments and runs validation functions."""
        self.override(overrides)
        self.resolve_references()
        self.check_required_args()
        self.validate()

    def validate(self) -> None:
        """Run validation functions recursively"""
        # Run validation for this config
        if not isinstance(self._validate, UNSPECIFIED_TYPE):
            if not self._validate(self):
                raise ValidationError(f"Config validation failed for {self.to_dict()}")

        # Recursively validate sub-configs
        for field in get_all_fields(self).values():
            if isinstance(field, Config):
                field.validate()

            elif isinstance(field, Field) and not isinstance(field.validate, UNSPECIFIED_TYPE):
                if not field.validate(field.value):
                    raise ValidationError(f"Field validation failed for {field.value}")

    def override(self, overrides: list[str] = sys.argv[1:]) -> None:
        """Override values from commandline.
        'overrides' argument should be of the same format as sys.argv[1:], e.g. ["--a.b", "1"].
        Automatically prints help page if "--help" is in the overrides."""

        def extract_kv_pairs(overrides):
            pairs = []
            i = 0
            while True:
                if i >= len(overrides):
                    break
                assert overrides[i].startswith("--")
                if i + 1 < len(overrides) and not overrides[i + 1].startswith("--"):
                    pairs.append((overrides[i][2:], overrides[i + 1]))
                    i += 1
                else:
                    pairs.append((overrides[i][2:],))
                i += 1
            return pairs

        if "--help" in overrides:
            self.print_help()
            sys.exit(0)

        for pair in extract_kv_pairs(overrides):
            if len(pair) == 2:
                key, value = pair
            elif len(pair) == 1 and pair[0].startswith(BOOLEAN_NEGATED_FLAG_PREFIX):
                key = pair[0][len(BOOLEAN_NEGATED_FLAG_PREFIX) :]
                value = "False"
            else:
                key = pair[0]
                value = "True"

            # "." in key --> delegate to subconfig
            if "." in key:
                first_dot_idx = key.index(".")
                first_key, rest_key = key[:first_dot_idx], key[first_dot_idx + 1 :]

                # subconfig is a regular field
                if first_key in self._fields:
                    sub_cfg = self._fields[first_key]

                # subconfig is a group
                elif (
                    not isinstance(self._groups, UNSPECIFIED_TYPE)
                    and isinstance(self._current_group, str)
                    and first_key in self._groups[self._current_group]._fields
                ):
                    sub_cfg = self._groups[self._current_group]._fields[first_key]

                # key neither in _fields not in _fields of current group
                else:
                    raise OverrideError(f"Override key '{first_key}' not found")

                if not isinstance(sub_cfg, Config):
                    raise OverrideError(f"Field '{first_key}' is not a Config")

                sub_cfg.override([f"--{rest_key}", value])

            # key does not have "." --> override value here
            else:
                if key in self._fields:
                    child = self._fields[key]

                elif (
                    not isinstance(self._groups, UNSPECIFIED_TYPE)
                    and isinstance(self._current_group, str)
                    and key in self._groups[self._current_group]._fields
                ):
                    child = self._groups[self._current_group]._fields[key]

                else:
                    raise OverrideError(f"Override key '{key}' not found")

                # regular field override
                if isinstance(child, Field):
                    child.value = child.convert_value(value)

                # switch groups override
                elif isinstance(child, Config):
                    if isinstance(child._groups, UNSPECIFIED_TYPE):
                        raise OverrideError("Can't override config unless it has groups")
                    elif value not in child._groups:
                        raise OverrideError(f"Group '{value}' does not exist")
                    child._current_group = value

    def resolve_references(self, _root: "Config | UNSPECIFIED_TYPE" = UNSPECIFIED) -> None:
        """Recursively run 'reference' and 'root_reference' functions"""
        if isinstance(_root, UNSPECIFIED_TYPE):
            _root = self

        for field in get_all_fields(self).values():
            if isinstance(field, Field) and not isinstance(field.reference, UNSPECIFIED_TYPE):
                field.value = field.reference(self)

            elif isinstance(field, Field) and not isinstance(field.reference_root, UNSPECIFIED_TYPE):
                field.value = field.reference_root(_root)

            elif isinstance(field, Config):
                field.resolve_references(_root=_root)

    def print_help(self, _path: str = "", _group_prefix: str = "", _root: bool = True) -> None:
        """Print help page for CLI."""
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
        """Create Config from dict recursively.
        Config(a=1, b=Config(c=2, d=4)) == Config.from_dict({"a": 1, "b": {"c": 2, "d": 4}})"""
        cfg_dict = {k: v if not isinstance(v, dict) else Config.from_dict(v) for k, v in d.items()}
        return Config(**cfg_dict)  # type: ignore

    def to_dict(self) -> dict:
        """Convert config to dict {field_name: field.value}.
        Resulting dict does not include extra features like validation or reference lambdas, just field names and values."""

        def format_value(v):
            if isinstance(v, Field):
                return v.value

            elif (  # if a group config has a literal value instead of a config, we return it directly
                isinstance(v, Config)
                and not v._fields
                and not isinstance(v._groups, UNSPECIFIED_TYPE)
                and isinstance(v._current_group, str)
                and not isinstance(v._groups[v._current_group], Config)
            ):
                return v._groups[v._current_group]

            elif isinstance(v, Config):
                return v.to_dict()
            else:
                return v

        return {k: format_value(v) for k, v in get_all_fields(self).items()}

    def to_yaml(self) -> str:
        """Convert config to YAML.
        This is not intended as re-loadable serialization, but merely as a readable representation of the config!
        To save and load your config later, use `.to_pickle` instead."""

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

    def to_pickle(self, path: str | Path) -> None:
        """Pickle the config using dill."""
        with open(path, "wb") as fp:
            dill.dump(self, fp, dill.HIGHEST_PROTOCOL)

    @staticmethod
    def from_pickle(path: str | Path) -> "Config":
        """Load pickled config using dill"""
        with open(path, "rb") as fp:
            cfg = dill.load(fp, dill.HIGHEST_PROTOCOL)
        return cfg

    def __getstate__(self) -> object:
        return self.__dict__

    def __setstate__(self, state) -> None:
        self.__dict__ = state

    def __repr__(self) -> str:
        """Use yaml formatting as readable representation of a config. Might change in the future."""
        return f"Config({self.to_dict()})"

    def __getattr__(self, __name: str) -> Any:
        """Allow direct member access to fields. Is only called if the name could not be found in the config object."""
        all_fields = get_all_fields(self)
        if __name in all_fields:
            v = all_fields[__name]
            if isinstance(v, Field):
                return v.value
            elif isinstance(v, Config):
                return v
            else:
                raise Exception("field values should only be Field's or Config's?")

        raise AttributeError(f"{__name} not found. Fields: {list(self._fields.keys())}")

    def __setattr__(self, __name: str, __value: Any) -> None:
        """Sets the value for a field.
        This automatically triggers the validation on the config and the field."""
        if __name in {
            "_validate",
            "_groups",
            "_from_signature",
            "_current_group",
            "_fields",
        } or __name.startswith("__"):
            super().__setattr__(__name, __value)
            return

        all_fields = get_all_fields(self)

        if __name in all_fields:
            orig_value = all_fields[__name].value
            all_fields[__name].value = __value
            if not isinstance(self._validate, UNSPECIFIED_TYPE):
                if not self._validate(self):
                    msg = f"Config validation failed for {self.to_dict()}"
                    all_fields[__name].value = orig_value
                    raise ValidationError(msg)
        else:
            raise AttributeError(f"{__name} not found")

    def __eq__(self, other):
        """Check equality using to_dict"""
        if not isinstance(other, Config):
            return False

        return self.to_dict() == other.to_dict()


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

        elif value in SPECIAL_VALUES:
            value = SPECIAL_VALUES[value]

        elif not isinstance(self.type, UNSPECIFIED_TYPE) and callable(self.type):
            try:
                value = self.type(value)
            except:  # noqa
                pass

        return value

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        self._value = v

    def __repr__(self):
        return repr(self.value)
