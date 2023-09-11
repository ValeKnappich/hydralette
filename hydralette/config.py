import builtins
import copy
import inspect
import logging
import sys
from collections import defaultdict
from dataclasses import MISSING as DC_MISSING
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Type, TypeVar, Union, get_args, get_origin

import yaml

from hydralette.exceptions import HydraletteConfigurationError
from hydralette.field import HydraletteField, field, fields

T = TypeVar("T")


class MISSING_TYPE(object):
    def __repr__(self):
        return "MISSING"


MISSING = MISSING_TYPE()

log = logging.getLogger(__name__)


class ConfigMeta(type):
    def __new__(cls, clsname, bases, attrs):
        cls = super().__new__(cls, clsname, bases, attrs)

        # try to infer type annotations if missing from groups, defaults and default_factories
        annotations = copy.deepcopy(cls.__annotations__)
        additional_annotations = {}
        for key, value in cls.__dict__.items():
            if key in annotations or key.startswith("__") or not isinstance(value, HydraletteField):
                continue
            if value.groups:
                additional_annotations[key] = Union[tuple(value.groups.values())]  # type: ignore
            elif value.default_factory not in (MISSING, DC_MISSING):
                additional_annotations[key] = type(value.default_factory())
            elif value.default not in (MISSING, DC_MISSING):
                additional_annotations[key] = type(value.default)
        cls.__annotations__ = {**cls.__annotations__, **additional_annotations}

        cls = dataclass(cls)
        for key, f in cls.__dataclass_fields__.items():
            if not isinstance(f, HydraletteField):
                hydralette_field = HydraletteField.from_dc_field(f)
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
        for f in fields(cls):
            if f.name not in sub_config_overrides and f.groups:
                kwargs[f.name] = f.default()  # type: ignore

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
            elif hasattr(t, "__name__"):
                return t.__name__
            else:
                return ""

        def print_options_for_class(cls, trace, group_info="", super_class=None):
            if cls in printed:
                return

            if group_info:
                group_info = f" ({group_info})"
            name = cls.__module__ + "." + cls.__name__
            print(f"Options from '{name}'{group_info}:")

            for f in fields(cls):
                if super_class is not None and f.name in [f.name for f in fields(super_class)]:
                    continue

                help = f.metadata.get("help", "")
                if is_hydralette_config(f.type) and help:
                    arg_descr = f"Options see below. {help}"
                elif is_hydralette_config(f.type) and not help:
                    arg_descr = "Options see below."
                else:
                    arg_descr = help

                _trace = trace + "." if trace else ""
                type_fmt = format_type_info(f.type)
                default = ""
                if f.default is not DC_MISSING:
                    default = f" = {f.default}"
                elif f.default_factory is not DC_MISSING:
                    df_name = f.default_factory.__name__  # type: ignore
                    if df_name == "<lambda>":
                        df = inspect.getsource(f.default_factory)
                        df = df[df.find("lambda") :].strip()
                        if df == "lambda: T()":
                            df = f"lambda: {f.type.__name__}()"
                    else:
                        df = f"{df_name}()"
                    default = f" = {df}"
                arg_name = f"{_trace}{f.name}: {type_fmt}{default} "
                print(f"\t{arg_name:70s}{arg_descr}")

            printed.append(cls)
            print()
            sub_config_fields = [field for field in fields(cls) if is_hydralette_config(field.type)]
            for f in sub_config_fields:
                _trace = trace + "." if trace else ""
                if f.groups:
                    for key, typ in f.groups.items():
                        print_options_for_class(typ, f"{_trace}{f.name}", f"active if '{f.name}={key}'")
                else:
                    print_options_for_class(f.type, f"{_trace}{f.name}")

        print(f"Usage: python {sys.argv[0]} [option=value]\n")
        print_options_for_class(cls, "")

    @classmethod
    def class_validation(cls):
        for f in fields(cls):
            # Check that groups have a default config class
            if f.groups and not (isinstance(f.default, type) and issubclass(f.default, ConfigBase)):
                raise HydraletteConfigurationError(
                    f"'{cls.__module__}.{cls.__name__}.{f.name}' is a group"
                    " but no proper default value is supplied. Pass the default config class (not instance!) "
                    "as default argument: 'default=YourDefaultConfig'."
                )

    def instance_validation(self):
        for f in fields(self):
            cls = self.__class__
            value = getattr(self, f.name)

            # Check for missing arguments
            if value is MISSING:
                raise HydraletteConfigurationError(
                    f"'{cls.__module__}.{cls.__name__}' is missing the required argument '{f.name}'"
                )

            if f.validate is not None and not f.validate(value):
                raise HydraletteConfigurationError(
                    f"Value '{value}' invalid for argument '{f.name}' in '{cls.__module__}.{cls.__name__}'"
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

        for f in fields(self):  # type: ignore
            value = getattr(self, f.name)
            if f.reference is not None:
                setattr(self, f.name, f.reference(root_config))
            elif is_hydralette_config(value):
                value.resolve_references(root_config=root_config)

    def __getattribute__(self, __name: str) -> Any:  # silence static type checker when fields from signature are accessed
        return super().__getattribute__(__name)


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


def config_from_signature(callable: Callable) -> Type[ConfigBase]:
    annotations = {
        parameter.name: parameter._annotation if parameter._annotation is not inspect._empty else Any
        for parameter in inspect.signature(callable)._parameters.values()  # type: ignore
    }

    dunders = {"__annotations__": annotations}
    if hasattr(callable, "__module__"):
        dunders["__module__"] = callable.__module__  # type: ignore

    fields = {
        parameter.name: field(default=parameter.default if parameter.default is not inspect._empty else MISSING)
        for parameter in inspect.signature(callable)._parameters.values()  # type: ignore
    }

    T = type(f"{callable.__name__}Hydralette", (ConfigBase,), {**dunders, **fields})
    return T
