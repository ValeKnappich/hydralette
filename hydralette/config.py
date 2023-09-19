import builtins
import copy
import inspect
import itertools
import logging
import sys
from collections import defaultdict
from dataclasses import _FIELDS  # type: ignore
from dataclasses import MISSING as DC_MISSING
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
    get_args,
    get_origin,
)

import yaml

from hydralette.exceptions import HydraletteConfigurationError
from hydralette.hydralette_field import HydraletteField, field, fields

T = TypeVar("T")


class MISSING_TYPE(object):
    def __repr__(self):
        return "MISSING"


MISSING = MISSING_TYPE()
"""Flag to indicate that a field is required."""

log = logging.getLogger(__name__)


class ConfigMeta(type):
    """Meta class for ConfigBase. Automatically infers annotations based on groups and defaults,
    applies the `dataclass` decorator and converts `Field`s into `HydraletteField`s.
    """

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
    """Base Class for hydralette configs.

    Create a subclass of this and define fields just like with dataclasses.

    Example:
        ```python
        from hydralette import ConfigBase, field

        class Config(ConfigBase):
            x: int = field(
                default=1,
                validate=lambda x: x > 0
            )
        ```

    Warning:
        Using the constructor to instantiate a config is not recommended. Use `ConfigClass.create` to use hydralettes full features.

    """

    @classmethod
    def create(cls: Type[T], overrides: List[str] = sys.argv[1:], yaml_overrides: Optional[dict] = None) -> T:
        """Entry point to instantiate a config.

        Args:
            overrides (List[str], optional): Overrides in the format `arg.subarg=value`. Pass in the path to a yaml override file with `--overrides <path>`. Help page is printed if it contains `"-h"` or `"--help"`. Defaults to `sys.argv[1:]`.
            yaml_overrides (dict, optional): YAML overrides as dict. Can alternatively be passed in the cli args via `--overrides=<path to yaml>`

        Raises:
            ValueError: If `cls` is not a subclass of ConfigBase
            SystemExit: After printing the help page

        Returns:
            T: Instance of the ConfigClass
        """
        if yaml_overrides is None:
            yaml_overrides = {}

        if not issubclass(cls, ConfigBase):
            raise ValueError(f"Type '{cls}' is not a subclass of ConfigBase")

        for help_flag in ("--help", "-h"):
            if help_flag in overrides:
                cls.print_help_page()
                raise SystemExit(0)

        if "--overrides" in overrides:  # syntax --overrides <path>
            if yaml_overrides:
                log.warning(
                    "YAML overrides are specified both from '--overrides <path>' and '.create(yaml_overrides=...)'."
                    "Using '--overrides' by default."
                )
            overrides_idx = overrides.index("--overrides") + 1
            yaml_path = Path(overrides[overrides_idx])
            yaml_overrides = yaml.safe_load(yaml_path.read_text())
            overrides = overrides[: overrides_idx - 1] + overrides[overrides_idx + 1 :]

        for overrides_idx, override in enumerate(overrides):
            if override.startswith("--overrides="):  # syntax --overrides=<path>
                if yaml_overrides:
                    log.warning(
                        "YAML overrides are specified both from '--overrides=<path>' and '.create(yaml_overrides=...)'."
                        "Using '--overrides' by default."
                    )
                yaml_path = Path(override.split("--overrides=")[1])
                yaml_overrides = yaml.safe_load(yaml_path.read_text())
                overrides = overrides[:overrides_idx] + overrides[overrides_idx + 1 :]
                break

        merged_overrides = cls.merge_overrides(cli_overrides=overrides, yaml_overrides=yaml_overrides)  # type: ignore
        config = cls.parse_and_instantiate(merged_overrides)
        config._overrides = merged_overrides  # type: ignore
        config.resolve_references()
        config.instance_validation()
        return config

    @classmethod
    def merge_overrides(cls, cli_overrides: List[str], yaml_overrides: dict) -> dict:
        """Merge CLI and YAML overrides into YAML format

        Args:
            cli_overrides (List[str]): _description_
            yaml_overrides (dict): _description_

        Returns:
            dict: merged overrides
        """

        for cli_override in cli_overrides:
            current_d = yaml_overrides

            key, value = cli_override.split("=")
            subkeys = key.split(".")

            for i in itertools.count():  # iterate like this to be able to change the iterable during iteration
                if i > len(subkeys) - 1:
                    break

                if subkeys[i] not in current_d:
                    current_d[subkeys[i]] = {}

                if i != len(subkeys) - 1:
                    current_d = current_d[subkeys[i]]
                elif (
                    hasattr((current_field := getattr(cls, _FIELDS, {}).get(subkeys[i])), "groups")
                    and isinstance(current_field, HydraletteField)
                    and current_field.groups != {}
                ):
                    current_d = current_d[subkeys[i]]
                    subkeys.append("__group__")
                else:
                    current_d[subkeys[-1]] = value
        return yaml_overrides

    @classmethod
    def parse_and_instantiate(cls: Type[T], overrides: dict) -> T:
        """Parse overrides and recursively instantiate config.

        Args:
            overrides (dict): Merged overrides, same format as YAML overrides.

        Raises:
            ValueError: _description_
            HydraletteConfigurationError: _description_

        Returns:
            ConfigBase: instantiated config
        """
        kwargs = {}
        nested_defaultdict = lambda: defaultdict(nested_defaultdict)
        sub_config_overrides = nested_defaultdict()
        sub_config_types = defaultdict()

        for key, value in overrides.items():
            matched_fields = [field for field in fields(cls) if field.name == key]
            if not matched_fields:
                raise ValueError(f"Key '{key}' could not be found in {cls}")
            matched_field = matched_fields[0]

            if isinstance(value, dict):
                if key not in sub_config_types:
                    if matched_field.groups:
                        if "__group__" in value:
                            group_key = value.pop("__group__")
                            if group_key not in matched_field.groups:
                                raise HydraletteConfigurationError(
                                    f"Invalid group '{value}' for field '{matched_field.name}' "
                                    f"in '{cls.__module__}.{cls.__name__}'"
                                )
                            field_type = matched_field.groups[group_key]
                        else:
                            field_type = matched_field.default
                    else:
                        field_type = matched_field.type
                    sub_config_types[key] = field_type
                sub_config_overrides[key] = value  # type: ignore
            else:
                kwargs[key] = convert_type(matched_field, value)

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
        """Print the help page. Is called automatically by `.create()` if `-h` or `--help` is in the overrides."""
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
                    default = f" = {f.default_factory()}"
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
        """Validate that the config class is defined correctly.

        - Check that group fields have a default that is also a config class.
        """
        for f in fields(cls):
            # Check that groups have a default config class
            if f.groups and not (isinstance(f.default, type) and issubclass(f.default, ConfigBase)):
                raise HydraletteConfigurationError(
                    f"'{cls.__module__}.{cls.__name__}.{f.name}' is a group"
                    " but no proper default value is supplied. Pass the default config class (not instance!) "
                    "as default argument: 'default=YourDefaultConfig'."
                )

    def instance_validation(self):
        """Validate that config was correctly instantiated. Checks if

        - all required args are provided
        - all validation lambdas pass
        """
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

    def to_dict(self, only_repr=False, recursive=True) -> Dict[str, Any]:
        """Convert config to dict. Optionally converts sub-configs to dicts as well.

        Args:
            only_repr (bool, optional): If true, all objects of non-builtin types are replaced by their repr. Useful for printing but not for serialization. Defaults to False.
            recursive (bool, optional): If true, the conversion it repeated recursively for sub-configs. Defaults to True.

        Returns:
            Dict[str, Any]: Converted config
        """
        if recursive:
            return {field.name: _get_attr(self, field.name, only_repr=only_repr) for field in fields(self)}
        else:
            return {field.name: getattr(self, field.name) for field in fields(self)}

    def to_yaml(self, sort_keys=False, only_repr=False) -> str:
        """Convert config to YAML format.

        Args:
            sort_keys (bool, optional): If true, keys are sorted alphabetically. Passed to `yaml.dump`. Defaults to False.
            only_repr (bool, optional): See `to_dict`. Defaults to False.

        Returns:
            str: Config in YAML format
        """
        d = self.to_dict(only_repr=only_repr)
        return yaml.dump(d, sort_keys=sort_keys)

    def print_yaml(self):
        """Prints the current config in YAML format with `only_repr=True`."""
        print(self.to_yaml(only_repr=True))

    def save(
        self,
        dir: Optional[Union[str, Path]] = None,
        config_name: str = "config.yaml",
        overrides_name: str = "overrides.yaml",
        defaults_name: str = "defaults.yaml",
    ) -> None:
        if dir is not None:
            config_path = Path(dir, config_name)
            overrides_path = Path(dir, overrides_name)
            defaults_path = Path(dir, defaults_name)
        else:
            config_path = Path(config_name)
            overrides_path = Path(overrides_name)
            defaults_path = Path(defaults_name)

        config_path.write_text(self.to_yaml())
        overrides_path.write_text(yaml.dump(self._overrides))
        defaults = self.__class__.parse_and_instantiate({}).to_yaml()
        defaults_path.write_text(defaults)

    def resolve_references(self, root_config=None):
        """Calls the reference lambdas on all fields.

        Args:
            root_config (_type_, optional): _description_. Defaults to None.
        """
        if root_config is None:
            root_config = self

        for f in fields(self):  # type: ignore
            value = getattr(self, f.name)
            if f.reference is not None:
                setattr(self, f.name, f.reference(root_config))
            elif is_hydralette_config(value):
                value.resolve_references(root_config=root_config)

    def __getattribute__(self, __name: str) -> Any:
        """Default method. Used to silence the static type checker when `from_signature` is used.

        Args:
            __name (str): _description_

        Returns:
            Any: _description_
        """
        return super().__getattribute__(__name)


def is_hydralette_config(obj: Any) -> bool:
    """Helper function to check if something is a hydralette config. Returns true if

    - `obj` is an instance of `ConfigBase` or
    - `obj` is a subclass of `ConfigBase` or
    - `obj` is a `typing.Union` of subclasses of `ConfigBase`

    Args:
        obj (Any): _description_

    Returns:
        bool: _description_
    """
    return (
        isinstance(obj, ConfigBase)
        or (isinstance(obj, type) and issubclass(obj, ConfigBase))
        or (get_origin(obj) is Union and all(issubclass(t, ConfigBase) for t in get_args(obj)))
    )


def convert_type(field: HydraletteField, value: str) -> Any:
    """Convert a value to a fields type. Tries field.convert if provided and field.type otherwise.

    Args:
        field (HydraletteField): Field to get the type from
        value (str): Value from CLI

    Returns:
        Any: Converted value
    """
    if field.convert is not None:
        return field.convert(value)
    else:
        try:
            return field.type(value)
        except:  # noqa
            return value


def _get_attr(obj, name, only_repr=False):
    """Helper function to traverse config tree and convert to dict"""
    value = getattr(obj, name)
    if isinstance(value, ConfigBase):
        return value.to_dict()
    elif only_repr and not type(value).__name__ in dir(builtins):
        return repr(value)
    else:
        return value


def config_from_signature(callable: Callable) -> Type[ConfigBase]:
    """Generate a config from an arbitrary signature.

    Args:
        callable (Callable): Callable to get the signature from

    Returns:
        Type[ConfigBase]: Config Class
    """
    annotations = {
        parameter.name: parameter._annotation if parameter._annotation is not inspect._empty else Any
        for parameter in inspect.signature(callable)._parameters.values()  # type: ignore
    }

    dunders = {"__annotations__": annotations}
    if hasattr(callable, "__module__"):
        dunders["__module__"] = callable.__module__  # type: ignore

    fields = {}
    for parameter in inspect.signature(callable)._parameters.values():  # type: ignore

        def default_factory_generic(parameter):
            if parameter.default is not inspect._empty:
                return parameter.default
            return MISSING

        default_factory = partial(default_factory_generic, parameter=parameter)

        fields[parameter.name] = field(default_factory=default_factory, default=DC_MISSING)

    T = type(f"{callable.__name__}Hydralette", (ConfigBase,), {**dunders, **fields})
    return T
