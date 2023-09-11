import builtins
import sys
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Type, TypeVar, Union, get_args, get_origin

import yaml

from .exceptions import HydraletteConfigurationError
from .field import HydraletteField, fields

T = TypeVar("T")

MISSING = object()


class ConfigMeta(type):
    def __new__(cls, clsname, bases, attrs):
        cls = super().__new__(cls, clsname, bases, attrs)
        cls = dataclass(cls)
        for key, field in cls.__dataclass_fields__.items():
            if not isinstance(field, HydraletteField):
                hydralette_field = HydraletteField.from_dc_field(field)
                cls.__dataclass_fields__[key] = hydralette_field
        cls.class_validation()
        return cls


class ConfigBase(metaclass=ConfigMeta):
    @classmethod
    def create(cls: Type[T], overrides: List[str] = sys.argv[1:]) -> T:
        if not issubclass(cls, ConfigBase):
            raise ValueError(f"Type '{cls}' is not a subclass of ConfigBase")

        for help_flag in ("--help", "-h"):
            if help_flag in overrides:
                cls.print_help_page()
                raise SystemExit(0)

        config = cls.parse_and_instantiate(overrides)
        config.resolve_references()
        config.instance_validation()
        return config

    @classmethod
    def parse_and_instantiate(cls: Type[T], overrides: List[str] = sys.argv[1:]) -> T:
        kwargs = {}
        sub_config_overrides = defaultdict(list)
        sub_config_types = defaultdict()

        # parse overrides
        for override in overrides:
            key, value = override.split("=")
            subkeys = key.split(".")

            # Match key to the corresponding field
            matched_field = None
            matched_fields = [field for field in fields(cls) if field.name == key]
            matched_sub_fields = [field for field in fields(cls) if field.name == subkeys[0]]
            if matched_fields:
                matched_field = matched_fields[0]
                top_level = True
            elif matched_sub_fields:
                matched_field = matched_sub_fields[0]
                top_level = False
            else:
                raise ValueError(f"Key '{key}' could not be found in {cls}")

            # top level primitive assignments: key=val
            if top_level and not is_hydralette_config(matched_field.type):
                kwargs[key] = convert_type(matched_field, value)

            # config groups: key=group_name
            elif top_level and is_hydralette_config(matched_field.type):
                if value not in matched_field.groups:
                    raise HydraletteConfigurationError(
                        f"Invalid group '{value}' for field '{matched_field.name}' " f"in '{cls.__module__}.{cls.__name__}'"
                    )
                sub_config_types[key] = matched_field.groups[value]

            # sub level assignments: subkey[0].subkey[1]=val
            else:
                if subkeys[0] not in sub_config_types:
                    if matched_field.groups:
                        field_type = matched_field.default
                    else:
                        field_type = matched_field.type
                    sub_config_types[subkeys[0]] = field_type
                sub_config_overrides[subkeys[0]].append(f"{'.'.join(subkeys[1:])}={value}")

        # create sub configs that do not have overrides
        for field in fields(cls):
            if field.name not in sub_config_overrides and field.groups:
                kwargs[field.name] = field.default()  # type: ignore

        # create sub configs that have overrides
        for key, sub_cls in sub_config_types.items():
            kwargs[key] = sub_cls.parse_and_instantiate(sub_config_overrides[key])  # type: ignore

        config = cls(**kwargs)
        return config

    @classmethod
    def print_help_page(cls) -> None:
        printed = []

        def format_type_info(t) -> str:
            if get_origin(t) is Union:
                return f"Union[{', '.join(st.__name__ for st in get_args(t))}]"
            else:
                return t.__name__

        def print_options_for_class(cls, trace, group_info="", super_class=None):
            if cls in printed:
                return

            if group_info:
                group_info = f" ({group_info})"
            name = cls.__module__ + "." + cls.__name__
            print(f"Options from '{name}'{group_info}:")

            for field in fields(cls):
                if super_class is not None and field.name in [f.name for f in fields(super_class)]:
                    continue
                arg_descr = field.metadata.get("help", "") if not is_hydralette_config(field.type) else "Options see below"
                _trace = trace + "." if trace else ""
                type_fmt = format_type_info(field.type)
                arg_name = f"{_trace}{field.name}: {type_fmt}"
                print(f"\t{arg_name:55s}{arg_descr}")

            printed.append(cls)
            print()
            sub_config_fields = [field for field in fields(cls) if is_hydralette_config(field.type)]
            for field in sub_config_fields:
                _trace = trace + "." if trace else ""
                if field.groups:
                    for key, typ in field.groups.items():
                        print_options_for_class(typ, f"{_trace}{field.name}", f"active if '{field.name}={key}'")
                else:
                    print_options_for_class(field.type, f"{_trace}{field.name}")

        print(f"Usage: python {sys.argv[0]} [option=value]\n")
        print_options_for_class(cls, "")

    @classmethod
    def class_validation(cls):
        for field in fields(cls):
            # Check that groups have a default config class
            if field.groups and not (isinstance(field.default, type) and issubclass(field.default, ConfigBase)):
                raise HydraletteConfigurationError(
                    f"'{cls.__module__}.{cls.__name__}.{field.name}' is a group"
                    " but no proper default value is supplied. Pass the default config class (not instance!) "
                    "as default argument: 'default=YourDefaultConfig'."
                )

    def instance_validation(self):
        for field in fields(self):
            cls = self.__class__
            value = getattr(self, field.name)

            # Check for missing arguments
            if value is MISSING:
                raise HydraletteConfigurationError(
                    f"'{cls.__module__}.{cls.__name__}' is missing the required argument '{field.name}'"
                )

            if field.validate is not None and not field.validate(value):
                raise HydraletteConfigurationError(
                    f"Value '{value}' invalid for argument '{field.name}' in '{cls.__module__}.{cls.__name__}'"
                )

            elif isinstance(value, ConfigBase):
                value.instance_validation()

    def to_dict(self, only_repr=False) -> Dict[str, Any]:
        return {field.name: _get_attr(self, field.name, only_repr=only_repr) for field in fields(self)}

    def to_yaml(self, sort_keys=False, only_repr=False) -> str:
        d = self.to_dict(only_repr=only_repr)
        return yaml.dump(d, sort_keys=sort_keys)

    def print_yaml(self):
        print(self.to_yaml(only_repr=True))

    def resolve_references(self, root_config=None):
        if root_config is None:
            root_config = self

        for field in fields(self):  # type: ignore
            value = getattr(self, field.name)
            if field.reference is not None:
                setattr(self, field.name, field.reference(root_config))
            elif is_hydralette_config(value):
                value.resolve_references(root_config=root_config)


def is_hydralette_config(obj: Any) -> bool:
    return (
        isinstance(obj, ConfigBase)
        or (isinstance(obj, type) and issubclass(obj, ConfigBase))
        or (get_origin(obj) is Union and all(issubclass(t, ConfigBase) for t in get_args(obj)))
    )


def convert_type(field: HydraletteField, value: str) -> Any:
    if field.convert is not None:
        return field.convert(value)
    else:
        try:
            return field.type(value)
        except:  # noqa
            return value


def _get_attr(obj, name, only_repr=False):
    value = getattr(obj, name)
    if isinstance(value, ConfigBase):
        return value.to_dict()
    elif only_repr and not type(value).__name__ in dir(builtins):
        return repr(value)
    else:
        return value
