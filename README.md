<div align="center" markdown="1">

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

- v0.2.3
    - change version of `dill` dependency
- v0.2.2
    - support mixing _fields, _groups and _from_signature
    - support literal values as groups
    - add boolean flags as `--flag` or `--no-flag`
- v0.2.1
    - fix yaml representation
    - support setting value to None in automatic conversion
- v0.2.0
    - complete re-design --> breaking changes!
    - easier creation of hierarchical configs
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


## Features

### Basics

Create a config using the `Config` class, passing the config fields as keyword arguments.

```python
from hydralette import Config
cfg = Config(a=1, b=2, c="abc")
```

`Config` objects can be create from and exported to `dict`s.

```python
from hydralette import Config
cfg = Config.from_dict({"a": 1, "b": 2, "c": "abc"})
print(cfg.to_dict())
```

Every hydralette `Config` be overriden via CLI:

```python
from hydralette import Config, Field
cfg = Config(
    a=Field(default=1, help="Lorem ipsum"),
    b=Config(
        c=Field(default=2, help="Lorem ipsum")
    )
)
cfg.apply(["--help"]) # or cfg.print_help()

# prints:

# Usage python script.py [OPTIONS]
# --a 1                   Lorem ipsum
# --b.c 1                 Lorem ipsum
```

After creation, you can override, resolve references, validate and check for missing required arguments.

```python
cfg.override(["--a", "1"]) # overrides defaults to sys.argv[1:]
cfg.resolve_references()
cfg.validate()
cfg.check_required_args()
# OR
cfg.apply(["--a", "1"]) # shorthand for the above
```


### Groups

Config groups can be very handy to make components interchangeable without requiring them to share a config.

```python
from hydralette import Config, Field
cfg = Config(
    model=Config(
        _groups={
            "_default": "rnn",
            "rnn": Config(
                n_layers=2,
                bidirectional=False
            ),
            "transformer": Config(
                n_layers=16,
                num_attention_heads=8
            )
        }
    )
)
cfg.apply(["--model", "transformer"])
```

### From signature / existing config

Often times, part of your configuration is already implemented somewhere else and duplicating this information creates a source of failure. Instead, you can automatically generate your hydralette `Config` based on an existing interface

```python

def calc(a: int, b=2):
    pass

from hydralette import Config, Field
cfg = Config(_from_signature=calc)
# equivalent to
cfg = Config(a=Field(type=int), b=Field(default=2, type=int))
```


### Fields

When you directly pass a value to `Config`s constructor, hydralette will create a `Field` under the hood. To use additional features, you can create it explicitly

`convert`: Specify how command-line overrides should be converted to the target type. If not explicitly specified, hydralette tries to use the field's `type` as conversion function (`type` is either explicitly specified or automatically derived from `default` / `default_factory`).

```python
import json
from hydralette import Config, Field
cfg = Config(my_dict=Field(default={"a": 1, "b": {"c": 2}}, convert=json.loads))
cfg.apply(['--my_dict', r'{"a": 2, "b": {"c": 3}}'])
```

`validate`: Constrain what values are valid for your field. If the validity of a value depends on the rest of the config, use `_validate` in the `Config` constructor instead.

```python
from hydralette import Config, Field
cfg = Config(n=Field(default=1, validate=lambda n: n > 0))
cfg.apply(['--n', '-1'])
# throws: ValidationError: Field validation failed for -1
cfg = Config(_validate=lambda cfg: cfg.a > cfg.b, a=1, b=2)
cfg.apply() # or cfg.validate()
# throws: ValidationError: Config validation failed for {'a': 1, 'b': 2}
```

`reference` / `reference_root`: Refer to any other value in the config

```python
from hydralette import Config, Field
from pathlib import Path
cfg = Config(
    dir=Path("outputs"),
    train=Config(
        checkpoint_dir=Field(reference_root=lambda cfg: cfg.dir / "checkpoints"), # relative to current config
        metrics_dir=Field(reference=lambda cfg: cfg.checkpoint_dir.parent / "metrics") # relative to root config
    )
)
cfg.resolve_references()
```





## Backlog

- [x] CLI
- [x] groups
- [x] from signatures
- [x] validation
- [x] conversion
- [x] references
- [x] yaml representation
- [x] pickle serialization
- [x] allow combining _groups, _fields and _from_signature
- [x] special support for boolean flags in CLI

## Dev Info

Steps on new release:

1. Run tests `pytest`
2. Edit docs
3. Increment version in `pyproject.toml`
4. Add changelog to `README.md`
5. Push increment to GitHub
6. Publish to PyPI `poetry publish --build`
7. Publish docs `mkdocs gh-deploy`
8. Create release and tag on GitHub