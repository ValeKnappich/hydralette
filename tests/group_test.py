from pathlib import Path
from typing import Union

import pytest

from hydralette import ConfigBase, HydraletteConfigurationError, field


class TransformerModelConfig(ConfigBase):
    n_layers: int = field(default=32, metadata=dict(help="Number of Transformer Layers"))
    num_attention_heads: int = field(default=8, metadata=dict(help="Number of Attention Heads per Layer"))


class RNNModelConfig(ConfigBase):
    n_layers: int = field(default=4, metadata=dict(help="Number of RNN Layers"))
    bidirectional: bool = field(default=True, metadata=dict(help="Bidirectional or Unidirectional RNN Layers"))


class Config(ConfigBase):
    output_dir: Path = field(default=Path("output"), metadata=dict(help="Output directory to save all results to"))
    model: Union[TransformerModelConfig, RNNModelConfig] = field(
        default=RNNModelConfig,
        metadata=dict(help="Config for model"),
        groups=dict(transformer=TransformerModelConfig, rnn=RNNModelConfig),
    )


def test_default_group():
    config = Config.create()
    assert config.to_dict() == {"output_dir": Path("output"), "model": {"n_layers": 4, "bidirectional": True}}


def test_changed_group():
    cli_args = "model=transformer model.num_attention_heads=16".split(" ")
    config = Config.create(cli_args)
    assert config.to_dict() == {"output_dir": Path("output"), "model": {"n_layers": 32, "num_attention_heads": 16}}


def test_nonexistent_group():
    with pytest.raises(HydraletteConfigurationError):
        cli_args = "model=thisdoesnotexist model.num_attention_heads=16".split(" ")
        config = Config.create(cli_args)  # noqa: F841
