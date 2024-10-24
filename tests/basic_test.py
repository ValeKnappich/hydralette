import json
import tempfile
from pathlib import Path

import pytest

from hydralette import Config, Field, MissingArgumentError, ValidationError


def test_basic():
    """Basic single-level test"""
    cfg = Config(a=1, b=2, c="abc")
    assert cfg.to_dict() == {"a": 1, "b": 2, "c": "abc"}


def test_convert_auto():
    """Test automatic conversion based on type"""
    cfg = Config(a=Field(default=1, help="Lorem ipsum"), b=Config(c=Field(default=2, help="Lorem ipsum")))
    cfg.apply(["--b.c", "4"])
    assert cfg.b.c == 4


def test_convert_custom():
    """Test custom conversion"""
    cfg = Config(my_dict=Field(default={"a": 1, "b": {"c": 2}}, convert=json.loads))
    cfg.apply(["--my_dict", r'{"a": 2, "b": {"c": 3}}'])
    assert cfg.my_dict == {"a": 2, "b": {"c": 3}}


def test_group():
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


def test_signature():
    """Test from signature"""

    def calc(a: int, b=2):
        pass

    cfg = Config(_from_signature=calc)
    cfg.apply(["--a", "42"])
    assert cfg.to_dict() == {"a": 42, "b": 2}


def test_validate():
    """Test validation"""
    cfg = Config(n=Field(default=1, validate=lambda n: n > 0))
    with pytest.raises(ValidationError):
        cfg.apply(["--n", "-1"])
        # throws: ValidationError: Field validation failed for -1

    cfg = Config(_validate=lambda cfg: cfg.a > cfg.b, a=1, b=2)
    with pytest.raises(ValidationError):
        cfg.apply()  # or cfg.validate()
        # throws: ValidationError: Config validation failed for {'a': 1, 'b': 2}


def test_references():
    """Test references"""
    cfg = Config(
        dir=Path("outputs"),
        train=Config(
            checkpoint_dir=Field(reference_root=lambda cfg: cfg.dir / "checkpoints"),  # relative to current config
            metrics_dir=Field(reference=lambda cfg: cfg.checkpoint_dir.parent / "metrics"),  # relative to root config
        ),
        # make sure reference fields can still be overridden
        sub_dir=Field(reference=lambda cfg: cfg.dir / "sub", type=Path),
        # but: types wont be automatically inferred from reference return type (value will be str when overriden without type or convert argument)
        sub_sub_dir=Field(reference=lambda cfg: cfg.dir / "sub" / "sub")
    )
    cfg.apply(["--sub_dir", "outputs/sub_2", "--sub_sub_dir", "outputs/sub_2/sub_2"])

    assert cfg.to_dict() == {
        "dir": Path("outputs"),
        "train": {"checkpoint_dir": Path("outputs/checkpoints"), "metrics_dir": Path("outputs/metrics")},
        "sub_dir": Path("outputs/sub_2"),
        "sub_sub_dir": "outputs/sub_2/sub_2",
    }


def test_None():
    """Test setting field to None"""
    cfg = Config(a=1)
    cfg.apply(["--a", "None"])
    assert cfg.a is None


def test_to_yaml():
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


def test_pickle():
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


def test_from_dict_equals():
    """Test from dict and equality"""
    assert Config(a=1, b=Config(c=2, d=4)) == Config.from_dict({"a": 1, "b": {"c": 2, "d": 4}})


def test_mix_group_fields():
    """Mix groups and fields, such that some fields are shared between groups"""

    cfg = Config(
        model=Config(
            n_layers=10,
            _groups={"_default": "rnn", "rnn": Config(bidirectional=False), "transformer": Config(n_attention_heads=8)},
        )
    )
    cfg.apply(["--model", "transformer"])
    assert cfg.to_dict() == {"model": {"n_layers": 10, "n_attention_heads": 8}}


def test_mix_fields_signature():
    def hello(a: int, b: float = 3.0, **kwargs):
        pass

    cfg = Config(_from_signature=hello, a=3)
    cfg.apply()
    assert cfg.to_dict() == {"a": 3, "b": 3.0, "kwargs": {}}


def test_non_config_group():
    cfg = Config(x=Config(_groups={"_default": "g1", "g1": Config(a=1, b=2), "none": 4}))
    assert cfg.to_dict() == {"x": {"a": 1, "b": 2}}
    cfg.apply(["--x", "none"])
    assert cfg.to_dict() == {"x": 4}


def test_missing_required_args():
    cfg = Config(
        a=Field(type=int),
        b=Config(
            _groups={
                "_default": "c",
                "c": Config(
                    a=Field(default=1),
                ),
                "d": Config(a=Field(type=int)),
            }
        ),
    )
    with pytest.raises(MissingArgumentError):
        cfg.apply()
    cfg.apply(["--a", "1"])
    cfg.apply(["--b", "c"])
    with pytest.raises(MissingArgumentError):
        cfg.apply(["--b", "d"])
    cfg.apply(["--b", "d", "--b.a", "4"])


def test_boolean_flag():
    cfg = Config(a=False, b=True)
    cfg.apply(["--a"])
    assert cfg.a is True
    cfg.apply(["--no-b"])
    assert cfg.b is False


if __name__ == "__main__":
    for n, f in {**locals()}.items():
        if callable(f) and ("test_" in n or "_test" in n):
            f()
