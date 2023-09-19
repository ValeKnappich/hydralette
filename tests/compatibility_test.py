from dataclasses import dataclass, field

from hydralette import ConfigBase, config_from_signature


@dataclass
class LibraryConfig:
    a: int = field(default=1, metadata=dict(help="a"))
    b: float = field(default=2.0, metadata=dict(help="b"))


class MyConfig(LibraryConfig, ConfigBase):
    pass


def my_function(a: int, b: float = 4.0, c: dict = {}):
    pass


def test_existing_dataclass():
    config = MyConfig.create(overrides=["a=5"])
    assert config.to_dict() == {"a": 5, "b": 2.0}


def test_existing_interface():
    config = config_from_signature(my_function).create(yaml_overrides={"a": 4})
    assert config.to_dict() == {"a": 4, "b": 4.0, "c": {}}
