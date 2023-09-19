import tempfile
from pathlib import Path
from typing import Union

import yaml

from hydralette import ConfigBase, field


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
    # Case 1: Mix cli with yaml, define group in yaml, no overlap
    yaml_overrides = yaml.dump({"model": {"n_layers": 32}})
    f = tempfile.NamedTemporaryFile("w")
    f.write(yaml_overrides)
    f.flush()
    overrides = ["output_dir=myoutput", "model=transformer", f"--overrides={f.name}"]
    config = Config.create(overrides)
    config.print_yaml()

    # Case 2: Mix cli with yaml, define group in cli, no overlap
    yaml_overrides = yaml.dump({"output_dir": "myoutput"})
    f = tempfile.NamedTemporaryFile("w")
    f.write(yaml_overrides)
    f.flush()
    overrides = ["model=transformer", "model.n_layers=32", f"--overrides={f.name}"]
    config = Config.create(overrides)
    config.print_yaml()

    # Case 3: Mix cli with yaml, define group in cli, with overlap
    yaml_overrides = yaml.dump({"output_dir": "myoutput", "model": {"n_layers": 64}})
    f = tempfile.NamedTemporaryFile("w")
    f.write(yaml_overrides)
    f.flush()
    overrides = ["model=transformer", "model.n_layers=65", f"--overrides={f.name}"]
    config = Config.create(overrides)
    config.print_yaml()
    config.save(".")


if __name__ == "__main__":
    main()
