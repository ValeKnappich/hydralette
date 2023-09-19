from pathlib import Path
from typing import Union

from hydralette import ConfigBase, field


class TransformerModelConfig(ConfigBase):
    n_layers: int = field(default=32, metadata=dict(help="Number of Transformer Layers"))
    num_attention_heads: int = field(default=8, metadata=dict(help="Number of Attention Heads per Layer"))


class RNNModelConfig(ConfigBase):
    n_layers: int = field(default=4, metadata=dict(help="Number of RNN Layers"))
    bidirectional: bool = field(default=True, metadata=dict(help="Bidirectional or Unidirectional RNN Layers"))


class Config(ConfigBase):
    model: Union[TransformerModelConfig, RNNModelConfig] = field(
        metadata=dict(help="Config for model"),
        groups=dict(transformer=TransformerModelConfig, rnn=RNNModelConfig),
        default=RNNModelConfig,
    )
    output_dir: Path = field(default=Path("output"), metadata=dict(help="Output directory to save all results to"))
    model_n_layers: int = field(reference=lambda cfg: cfg.model.n_layers)
    checkpoint_dir: Path = field(reference=lambda cfg: cfg.output_dir / "checkpoints")


def test_defaults():
    config = Config.create()
    assert config.to_dict() == {
        "model": {"n_layers": 4, "bidirectional": True},
        "output_dir": Path("output"),
        "model_n_layers": 4,
        "checkpoint_dir": Path("output/checkpoints"),
    }


def test_changed_ref():
    cli_args = "model.n_layers=8 output_dir=another_output_dir".split(" ")
    config = Config.create(cli_args)
    assert config.to_dict() == {
        "model": {"n_layers": 8, "bidirectional": True},
        "output_dir": Path("another_output_dir"),
        "model_n_layers": 8,
        "checkpoint_dir": Path("another_output_dir/checkpoints"),
    }
