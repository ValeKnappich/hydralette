from pathlib import Path

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
        convert=lambda value: Path(value).expanduser(),  # custom type conversion including expanduser
    )
    model: ModelConfig = field(default_factory=lambda: ModelConfig(), metadata=dict(help="Config for model"))


def main():
    # Specify a value that violates the validation constraint
    exc = None
    try:
        cli_args = "model.n_layers=-5".split(" ")
        config = Config.create(cli_args)
        config.print_yaml()
    except Exception as e:
        exc = e
    assert isinstance(exc, HydraletteConfigurationError)

    # Custom conversion should yield an absolute path with /home/<user>/mydir
    cli_args = "output_dir=~/mydir".split(" ")
    config = Config.create(cli_args)
    config.print_yaml()
    assert str(config.output_dir).startswith("/home") and str(config.output_dir).endswith("/mydir")


if __name__ == "__main__":
    main()
