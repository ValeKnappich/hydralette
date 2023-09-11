from pathlib import Path
from typing import Union

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


def main():
    print("↓ ↓ ↓ ↓ ↓ ↓ ↓ Help Page ↓ ↓ ↓ ↓ ↓ ↓ ↓ \n")
    Config.print_help_page()
    print("\n" * 3)

    # Correctly instantiate config with default arguments
    config = Config.create()
    config.print_yaml()
    assert config.to_dict() == {"output_dir": Path("output"), "model": {"n_layers": 4, "bidirectional": True}}
    print("\n" * 3)

    # Changing model group to transformer
    cli_args = "model=transformer model.num_attention_heads=16".split(" ")
    config = Config.create(cli_args)
    config.print_yaml()
    assert config.to_dict() == {"output_dir": Path("output"), "model": {"n_layers": 32, "num_attention_heads": 16}}

    # Changing model group to something that does not exist (should fail)
    cli_args = "model=thisdoesnotexist model.num_attention_heads=16".split(" ")
    exc = None
    try:
        config = Config.create(cli_args)
    except Exception as e:
        exc = e
    assert isinstance(exc, HydraletteConfigurationError)


if __name__ == "__main__":
    main()
