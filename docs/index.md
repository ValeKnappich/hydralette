<div markdown="1" align="center">

# Hydralette

**Create complex configurations in a simple, pythonic way!**

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

- [x] Build configs like dataclasses | [Example](examples/#minimal-example)
- [x] Automatically generate configs from class/function signatures | [Example](examples/#from-signature)
- [x] Effortless CLI from Config classes | [Example](examples/#cli)
- [x] Config groups to swap whole components | [Example](examples/#config-groups)
- [x] Referencing other config values to reduce redundancy | [Example](examples/#references)
- [x] Type Conversion from CLI | [Example](examples/#type-conversion)
- [x] Value Validation | [Example](examples/#validation)
- [x] Load and save yaml files
- [ ] Automatic instantiation

