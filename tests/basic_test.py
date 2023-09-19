from pathlib import Path

import pytest

from hydralette import MISSING, ConfigBase, HydraletteConfigurationError, field


class ModelConfig(ConfigBase):
    n_layers: int = field(default=32, metadata=dict(help="Number of Layers"))
    dropout: float = field(default=MISSING, metadata=dict(help="Dropout p value"))  # this is a required argument


class Config(ConfigBase):
    output_dir: Path = field(default=Path("output"), metadata=dict(help="Output directory to save all results to"))
    model: ModelConfig = field(default_factory=lambda: ModelConfig(), metadata=dict(help="Config for model"))


def test_cli_overrides():
    cli_args = "model.dropout=1e-5 output_dir=my_output_directory".split(" ")
    config = Config.create(cli_args)
    assert config.to_dict() == {"output_dir": Path("my_output_directory"), "model": {"n_layers": 32, "dropout": 1e-5}}


def test_yaml_overrides():
    yaml_overrides = {"model": {"dropout": 1e-5}, "output_dir": "my_output_directory"}
    config = Config.create(yaml_overrides=yaml_overrides)
    assert config.to_dict() == {"output_dir": Path("my_output_directory"), "model": {"n_layers": 32, "dropout": 1e-5}}


def test_missing_required_arg():
    with pytest.raises(HydraletteConfigurationError):
        cli_args = "output_dir=my_output_directory".split(" ")
        config = Config.create(cli_args)  # noqa: F841
