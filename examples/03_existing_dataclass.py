from dataclasses import dataclass, field

from hydralette import ConfigBase


# This could be defined in a library, i.e. pure dataclass
@dataclass
class LibraryConfig:
    a: int = field(default=1, metadata=dict(help="a"))
    b: float = field(default=2.0, metadata=dict(help="b"))


# To make a hydralette config from the pure dataclass, simply derive from both classes
class MyConfig(LibraryConfig, ConfigBase):
    pass


def main():
    print("↓ ↓ ↓ ↓ ↓ ↓ ↓ Help Page ↓ ↓ ↓ ↓ ↓ ↓ ↓ \n")
    MyConfig.print_help_page()

    config = MyConfig.create()
    config.print_yaml()
    assert config.to_dict() == {"a": 1, "b": 2.0}


if __name__ == "__main__":
    main()
