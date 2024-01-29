import json
from pathlib import Path

import pytest

from hydralette import Config, Field, ValidationError


def test_1():
    cfg = Config(a=1, b=2, c="abc")
    assert cfg.to_dict() == {"a": 1, "b": 2, "c": "abc"}


def test_2():
    cfg = Config(a=Field(default=1, help="Lorem ipsum"), b=Config(c=Field(default=2, help="Lorem ipsum")))
    cfg.apply(["--b.c", "4"])
    assert cfg.b.c == 4


def test_3():
    cfg = Config(
        model=Config(
            _groups={
                "_default": "rnn",
                "rnn": Config(n_layers=2, bidirectional=False),
                "transformer": Config(n_layers=16, num_attention_heads=8),
            }
        )
    )
    cfg.apply(["--model", "transformer"])
    assert cfg.to_dict() == {"model": {"n_layers": 16, "num_attention_heads": 8}}


def test_4():
    def calc(a: int, b=2):
        pass

    cfg = Config(_from_signature=calc)
    cfg.apply(["--a", "42"])
    assert cfg.to_dict() == {"a": 42, "b": 2}


def test_5():
    cfg = Config(my_dict=Field(default={"a": 1, "b": {"c": 2}}, convert=json.loads))
    cfg.apply(["--my_dict", r'{"a": 2, "b": {"c": 3}}'])
    assert cfg.my_dict == {"a": 2, "b": {"c": 3}}


def test_6():
    cfg = Config(n=Field(default=1, validate=lambda n: n > 0))
    with pytest.raises(ValidationError):
        cfg.apply(["--n", "-1"])
        # throws: ValidationError: Field validation failed for -1

    cfg = Config(_validate=lambda cfg: cfg.a > cfg.b, a=1, b=2)
    with pytest.raises(ValidationError):
        cfg.apply()  # or cfg.validate()
        # throws: ValidationError: Config validation failed for {'a': 1, 'b': 2}


def test_7():
    cfg = Config(
        dir=Path("outputs"),
        train=Config(
            checkpoint_dir=Field(reference_root=lambda cfg: cfg.dir / "checkpoints"),  # relative to current config
            metrics_dir=Field(reference=lambda cfg: cfg.checkpoint_dir.parent / "metrics"),  # relative to root config
        ),
    )
    cfg.resolve_references()

    assert cfg.to_dict() == {
        "dir": Path("outputs"),
        "train": {"checkpoint_dir": Path("outputs/checkpoints"), "metrics_dir": Path("outputs/metrics")},
    }
