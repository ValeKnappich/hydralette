<div align="center">

# Hydralette

**Create complex configurations in a simple, pythonic way!**

[![python](https://img.shields.io/badge/-Python_3.8_%7C_3.9_%7C_3.10-blue?logo=python&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![black](https://img.shields.io/badge/Code%20Style-Black-black.svg?labelColor=gray)](https://black.readthedocs.io/en/stable/)
[![isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)
[![license](https://img.shields.io/badge/License-MIT-green.svg?labelColor=gray)](https://github.com/ashleve/lightning-hydra-template#license)

<a href="https://valeknappich.github.io/hydralette" style="font-size: 14pt">Documentation</a>

</div>

## Installation

```bash
pip install hydralette
# OR
poetry add hydralette
```

## Changelog

- v0.1.5
    - Add yaml overrides
    - Add end-to-end tests with pytest
- v0.1.4
    - Add documentation at [https://valeknappich.github.io/hydralette](https://valeknappich.github.io/hydralette)
- v0.1.3
    - Add automatic generation of configs from signatures via `from_signature` and `config_from_signature`
- v0.1.2
    - Add support for `config groups`, `references`, `validation` and `type conversion`
    - Add CLI help pages

## Example

```python
from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Union

import yaml

from hydralette import ConfigBase, field


# lets assume this is defined in some library, i.e. you cant change the code
@dataclass
class LibraryConfig:
    a: int = 1
    b: float = 4.0


class LibraryConfigHydralette(LibraryConfig, ConfigBase): # <-- turn it into a hydralette config by subclassing
    pass


def some_function(a: int, b: float = 4.0): # <-- arbitrary interface that we can turn into a hydralette config
    pass


class TransformerModelConfig(ConfigBase):
    n_layers: int = field(
        default=32,
        metadata=dict(help="Number of Transformer Layers"),
        validate=lambda value: value > 0   # <-- validate config value
    )
    num_attention_heads: int = field(
        default=8,
        metadata=dict(help="Number of Attention Heads per Layer")
    )


class RNNModelConfig(ConfigBase):
    n_layers: int = field(
        default=4,
        metadata=dict(help="Number of RNN Layers")
    )
    bidirectional: bool = field(
        default=True,
        metadata=dict(help="Bidirectional or Unidirectional RNN Layers")
    )


class Config(ConfigBase):
    output_dir: Path = field(
        default=Path("output"),
        metadata=dict(help="Output directory to save all results to"),
        convert=lambda path: Path(path).expanduser(),   # <-- custom conversion lambda, otherwise type hint is tried
    )
    model: Union[TransformerModelConfig, RNNModelConfig] = field(
        default=RNNModelConfig,     # <-- default group
        metadata=dict(help="Config for model"),
        groups=dict(transformer=TransformerModelConfig, rnn=RNNModelConfig),    # <-- define groups
    )
    library: LibraryConfigHydralette = field(
        default_factory=LibraryConfigHydralette,   # <-- regular hierarchical config
        metadata=dict(help="Config for library")
    )
    interface = field(
        from_signature=some_function,  # <-- use function signature to derive config
        metadata=dict(help="Config for some_function")
    )


if __name__ == "__main__":
    # you can print it explicitly, otherwise this is called
    # automatically with .create() if -h or --help are in the overrides
    Config.print_help_page()

    # instantiate the config with .create()!
    # there are 2 main ways of overriding values via CLI:
    # 1. load overrides from yaml file
    # 2. override individual values via key1.key2.key3=value

    # Save some overrides to YAML file
    yaml_overrides = {"output_dir": "myoutput", "model": {"n_layers": 64}}
    s = yaml.dump(yaml_overrides)
    f = tempfile.NamedTemporaryFile("w")
    f.write(s)
    f.flush()

    overrides = f"interface.a=3 --overrides {f.name}"
    config = Config.create(
        overrides=overrides.split(" "), # splitting by space mimics the format of sys.argv
        yaml_overrides=None # alternatively to specifying the yaml path to --overrides, you can also pass the dict here
    )
    config.print_yaml()
    config.save(".") # saves 3 files to the specified directory: config.yaml, defaults.yaml and overrides.yaml
```
