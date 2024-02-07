import json
import tempfile
from pathlib import Path

import pytest

from hydralette import Config, Field, ValidationError


def test_1():
    """Basic single-level test"""
    cfg = Config(a=1, b=2, c="abc")
    assert cfg.to_dict() == {"a": 1, "b": 2, "c": "abc"}


def test_2():
    """Test automatic conversion based on type"""
    cfg = Config(a=Field(default=1, help="Lorem ipsum"), b=Config(c=Field(default=2, help="Lorem ipsum")))
    cfg.apply(["--b.c", "4"])
    assert cfg.b.c == 4


def test_3():
    """Test config group"""
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
    """Test from signature"""

    def calc(a: int, b=2):
        pass

    cfg = Config(_from_signature=calc)
    cfg.apply(["--a", "42"])
    assert cfg.to_dict() == {"a": 42, "b": 2}


def test_5():
    """Test custom conversion"""
    cfg = Config(my_dict=Field(default={"a": 1, "b": {"c": 2}}, convert=json.loads))
    cfg.apply(["--my_dict", r'{"a": 2, "b": {"c": 3}}'])
    assert cfg.my_dict == {"a": 2, "b": {"c": 3}}


def test_6():
    """Test validation"""
    cfg = Config(n=Field(default=1, validate=lambda n: n > 0))
    with pytest.raises(ValidationError):
        cfg.apply(["--n", "-1"])
        # throws: ValidationError: Field validation failed for -1

    cfg = Config(_validate=lambda cfg: cfg.a > cfg.b, a=1, b=2)
    with pytest.raises(ValidationError):
        cfg.apply()  # or cfg.validate()
        # throws: ValidationError: Config validation failed for {'a': 1, 'b': 2}


def test_7():
    """Test references"""
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


def test_8():
    """Test setting field to None"""
    cfg = Config(a=1)
    cfg.apply(["--a", "None"])
    assert cfg.a is None


def test_9():
    """Test exporting to yaml"""

    class MyObj:
        def __repr__(self):
            return "MyObj"

    cfg = Config(
        a=1,
        sub=Config(_groups=dict(_default="a", a=Config(s1=1, s2=3), b=Config(s2=4, s1=5))),
        b=Config(c=Config(d=Config(e=Field(default=MyObj())))),
    )
    cfg.apply(["--sub", "b"])

    assert (
        cfg.to_yaml()
        == repr(cfg)
        == """
a: 1
sub:
  s2: 4
  s1: 5
b:
  c:
    d:
      e: MyObj
""".strip()
    )


def test_10():
    """Test pickle serialization"""
    cfg = Config(
        dir=Path("outputs"),
        train=Config(
            checkpoint_dir=Field(reference_root=lambda cfg: cfg.dir / "checkpoints"),  # relative to current config
            metrics_dir=Field(reference=lambda cfg: cfg.checkpoint_dir.parent / "metrics"),  # relative to root config
        ),
    )
    cfg.apply(["--dir", "outputs2"])
    tmp_file = tempfile.NamedTemporaryFile().name
    cfg.to_pickle(tmp_file)
    cfg2 = Config.from_pickle(tmp_file)
    assert cfg.dir == cfg2.dir
    assert "outputs2" in str(cfg.dir)
