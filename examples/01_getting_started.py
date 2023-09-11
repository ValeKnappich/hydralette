from pathlib import Path

from hydralette import MISSING, ConfigBase, HydraletteConfigurationError, field


class ModelConfig(ConfigBase):
    n_layers: int = field(default=32, metadata=dict(help="Number of Layers"))
    dropout: float = field(default=MISSING, metadata=dict(help="Dropout p value"))  # this is a required argument


class Config(ConfigBase):
    output_dir: Path = field(default=Path("output"), metadata=dict(help="Output directory to save all results to"))
    model: ModelConfig = field(default_factory=lambda: ModelConfig(), metadata=dict(help="Config for model"))


def main():
    print("↓ ↓ ↓ ↓ ↓ ↓ ↓ Help Page ↓ ↓ ↓ ↓ ↓ ↓ ↓ \n")
    Config.print_help_page()
    print("\n" * 3)

    # Correctly instantiate config with the
    # required argument model.dropout and the
    # optional argument output_dir
    cli_args = "model.dropout=1e-5 output_dir=my_output_directory".split(" ")
    config = Config.create(cli_args)
    config.model  # static type checker should show type ModelConfig
    config.print_yaml()
    assert config.to_dict() == {"output_dir": Path("my_output_directory"), "model": {"n_layers": 32, "dropout": 1e-5}}

    # Incorrectly instantiate config without the
    # required argument model.dropout and the
    exc = None
    try:
        cli_args = "output_dir=my_output_directory".split(" ")
        config = Config.create(cli_args)
        config.model  # static type checker should show type ModelConfig
    except Exception as e:
        exc = e
    assert isinstance(exc, HydraletteConfigurationError)


if __name__ == "__main__":
    main()
