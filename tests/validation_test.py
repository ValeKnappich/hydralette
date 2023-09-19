from pathlib import Path

import pytest

from hydralette import ConfigBase, HydraletteConfigurationError, field


class ModelConfig(ConfigBase):
    n_layers: int = field(
        default=32, metadata=dict(help="Number of Layers"), validate=lambda value: value > 0  # validation constrait
    )
    dropout: float = field(
        default=0.1,
        metadata=dict(help="Dropout p value"),
    )


class Config(ConfigBase):
    output_dir: Path = field(
        default=Path("~/output").expanduser(),
        metadata=dict(help="Output directory to save all results to"),
        convert=lambda value: Path(value).expanduser(),
    )
    model: ModelConfig = field(default_factory=lambda: ModelConfig(), metadata=dict(help="Config for model"))


def test_validation_error():
    cli_args = "model.n_layers=-5".split(" ")
    with pytest.raises(HydraletteConfigurationError):
        config = Config.create(cli_args)  # noqa: F841


def test_conversion():
    cli_args = "output_dir=~/mydir".split(" ")
    config = Config.create(cli_args)
    config.print_yaml()
    assert str(config.output_dir).startswith("/home") and str(config.output_dir).endswith("/mydir")
