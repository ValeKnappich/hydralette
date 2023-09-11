<div align="center">

# Hydralette

**Complex configuration made simple**


[![python](https://img.shields.io/badge/-Python_3.8_%7C_3.9_%7C_3.10-blue?logo=python&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![black](https://img.shields.io/badge/Code%20Style-Black-black.svg?labelColor=gray)](https://black.readthedocs.io/en/stable/)
[![isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)
[![license](https://img.shields.io/badge/License-MIT-green.svg?labelColor=gray)](https://github.com/ashleve/lightning-hydra-template#license)

</div>

## Installation

```bash
pip install hydralette
# OR
poetry add hydralette
```

## Changelog

- v0.1.3 at commit [`90655ca`](https://github.com/ValeKnappich/hydralette/tree/90655caee3a95f652008a10ca0d5964c01733d39)
    - Add automatic generation of configs from signatures via `from_signature` and `config_from_signature`
- v0.1.2 at commit [`5848f43`](https://github.com/ValeKnappich/hydralette/tree/5848f436cb20ac3389018fe6d399502e45b266e5)
    - Add support for `config groups`, `references`, `validation` and `type conversion`
    - Add CLI help pages

## Features

- [x] Build configs like dataclasses | [Brief Example](#minimal-example)
- [x] Automatically generate configs from class/function signatures | [Brief Example](#from-signature) | [Complete Example](examples/06_from_signature.py)
- [x] Effortless CLI from Config classes | [Brief Example](#cli)
- [x] Config groups to swap whole components | [Brief Example](#config-groups) | [Complete Example](examples/02_groups.py)
- [x] Referencing other config values to reduce redundancy | [Brief Example](#references) | [Complete Example](examples/04_references.py)
- [x] Type Conversion from CLI | [Brief Example](#type-conversion) | [Complete Example](examples/05_conversion_and_validation.py)
- [x] Value Validation | [Brief Example](#validation) | [Complete Example](examples/05_conversion_and_validation.py)
- [ ] Load and save yaml files
- [ ] Automatic instantiation


## Examples

### Minimal Example

Hydralette configs are defined similar to dataclasses. Instead of decorating your class with `@dataclass`, derive it from `ConfigBase`.

```python
from hydralette import ConfigBase, field, MISSING

class ModelConfig(ConfigBase):
    n_layers: int = field(
        default=32,
        metadata=dict(help="Number of Layers")
    )
    dropout: float = field(
        default=0.1,
        metadata=dict(help="Dropout p value")
    )

if __name__ == "__main__":
    config = ModelConfig.create()
```

### Hierarchical Configs

> :information_source: Complete example in [examples/01_getting_started.py](examples/01_getting_started.py)

```python
class ModelConfig(ConfigBase):
    n_layers: int = field(
        default=32,
        metadata=dict(help="Number of Layers")
    )
    dropout: float = field(
        default=0.1,
        metadata=dict(help="Dropout p value")
    )

class Config(ConfigBase):
    output_dir: Path = field(
        default=Path("output"),
        metadata=dict(help="Ouput directory to save all results to")
    )
    model: ModelConfig = field(  # <-- specify another config class as field type to make the config hierarchical
        default_factory=lambda: ModelConfig(),
        metadata=dict(help="Config for model")
    )
```


### From Signature

> :information_source: Complete example in [examples/06_from_signature](examples/06_from_signature)

> :warning: Static analysis and auto-complete does not work with dynamically generated config classes.

If you already have an interface defined in the signature of a class or function, you can directly create your config from that without the need for duplicate code.

```python
class Config(ConfigBase):
    myclass = field(
        from_signature=MyClass,  # <-- generate config class from constructor signature and use as field
        metadata=dict(help="This is helpful text"),
    )
    my_func = field(from_signature=my_func)  # <-- generate config class from function signature and use as field
```


### CLI

All config fields can be overriden via the CLI. To make a field mandatory set its default to `hydralette.MISSING`.


```python
from hydralette import ConfigBase, field, MISSING

class ModelConfig(ConfigBase):
    n_layers: int = field(
        default=32,
        metadata=dict(help="Number of Layers")
    )
    dropout: float = field(
        default=MISSING,     # <-- required argument
        metadata=dict(help="Dropout p value")
    )

class Config(ConfigBase):
    output_dir: Path = field(
        default=Path("output"),
        metadata=dict(help="Ouput directory to save all results to")
    )
    model: ModelConfig = field(
        default_factory=lambda: ModelConfig(),
        metadata=dict(help="Config for model")
    )

if __name__ == "__main__":
    config = Config.create()
```

```bash
$ python example.py -h
Usage: python test.py [option=value]

Options from '__main__.Config':
        output_dir: Path                                       Ouput directory to save all results to
        model: ModelConfig                                     Options see below

Options from '__main__.ModelConfig':
        model.n_layers: int                                    Number of Layers
        model.dropout: float                                   Dropout p value
```

### Config Groups

> :information_source: Complete example in [examples/02_groups.py](examples/02_groups.py)

When configuring heterogeneous applications with interchangable parts, shared configurations can get messy. Different components might fulfill the same purpose but still require very different configuration paramters. Hydralette supports config groups to disentangle such configs. Components can then swapped with a single CLI override.

```python
class TransformerModelConfig(ConfigBase):
    n_layers: int = field(
        default=32,
        metadata=dict(help="Number of Transformer Layers")
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
        metadata=dict(help="Ouput directory to save all results to")
    )
    model: Union[TransformerModelConfig, RNNModelConfig] = field(
        default=RNNModelConfig,                                              # <-- default config class
        metadata=dict(help="Config for model"),
        groups=dict(transformer=TransformerModelConfig, rnn=RNNModelConfig), # <-- <key>=<config class>
    )

if __name__ == "__main__":
    config = Config.create()
    config.print_yaml()
```

```bash
$ python test.py model=transformer

output_dir: PosixPath('output')
model:
  n_layers: 32
  num_attention_heads: 8
```


### Compatibility with pure dataclasses

> :information_source: Complete example in [examples/03_existing_dataclass.py](examples/03_existing_dataclass.py)

Some libraries define their configuration as dataclasses. To use an existing dataclass as hydralette config, simply derive from it and `ConfigBase`.

```python
from library import LibraryConfig

class MyConfig(LibraryConfig, ConfigBase):
    pass
```

### References

> :information_source: Complete example in [examples/04_references.py](examples/04_references.py)

Sometimes a configuration value is required by multiple components. To avoid defining and overriding it in multiple places, simply reference a single source of truth. The `reference` API works with functions that take the main config as input and output and arbitrary value, so you can add things and combine multiple other values.

```python
class Config(ConfigBase):
    output_dir: Path = field(
        default=Path("output"),
        metadata=dict(help="Output directory to save all results to")
    )
    run_name: str = field(
        default="run-001",
        metadata=dict(help="Name of the run")
    )
    checkpoint_dir: Path = field(
        reference=lambda cfg: cfg.output_dir / cfg.run_name / "checkpoints"
    )
```

### Type Conversion

Values from the CLI need to converted to their correct type. If the type annotation already works as converter, types will be automatically converted. Alternatively, you can also provide a conversion function via `convert`.

```Python
class Config(ConfigBase):
    output_dir: Path = field(
        default=Path("~/output").expanduser(),
        metadata=dict(help="Output directory to save all results to"),
        convert=lambda value: Path(value).expanduser()      # custom type conversion to add expanduser
    )
```

### Validation

Every field can be validated by passing a lambda with signature `(value) -> (bool)` to `validate`.

```python
class Config(ConfigBase):
    n_layers: int = field(
        default=32,
        metadata=dict(help="Number of Layers"),
        validate=lambda value: value > 0
    )
```
