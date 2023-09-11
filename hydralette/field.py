from dataclasses import MISSING, Field
from dataclasses import fields as dc_fields
from typing import Any, Callable, Dict, Optional, Tuple


def field(
    *,
    reference: Optional[Callable] = None,
    convert: Optional[Callable] = None,
    validate: Optional[Callable] = None,
    groups: Dict[str, type] = {},
    default=MISSING,
    default_factory=MISSING,
    init=True,
    repr=True,
    hash=None,
    compare=True,
    metadata=None,
    kw_only=MISSING,
) -> Any:
    if reference is not None and default is MISSING and default_factory is MISSING:
        # Avoid error from dataclasses that non-default arguments cannot follow default arguments
        # default value is irrelevant anyway, since the value will be determined by the reference lambda
        default = None

    return HydraletteField(
        reference=reference,
        convert=convert,
        validate=validate,
        groups=groups,
        default=default,
        default_factory=default_factory,
        init=init,
        repr=repr,
        hash=hash,
        compare=compare,
        metadata=metadata,
        kw_only=kw_only,
    )


class HydraletteField(Field):
    """Field subclass that adds
    - referencing other values
    - type conversion functions
    - validation functions
    - config group information
    """

    def __init__(
        self,
        *,
        reference: Optional[Callable] = None,
        convert: Optional[Callable] = None,
        validate: Optional[Callable] = None,
        groups: Dict[str, type] = {},
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.reference = reference
        self.convert = convert
        self.validate = validate
        self.groups = groups

    @classmethod
    def from_dc_field(cls: type["HydraletteField"], field: Field) -> "HydraletteField":
        hydralette_field = cls(
            default=field.default,
            default_factory=field.default_factory,
            init=field.init,
            repr=field.repr,
            hash=field.hash,
            compare=field.compare,
            metadata=field.metadata,
            kw_only=field.kw_only,
        )
        hydralette_field.name = field.name
        hydralette_field.type = field.type  # type: ignore
        hydralette_field._field_type = field._field_type  # type: ignore

        return hydralette_field

    def __repr__(self):
        return (
            "HydraletteField("
            f"name={self.name!r},"
            f"type={self.type!r},"
            f"default={self.default!r},"
            f"default_factory={self.default_factory!r},"
            f"init={self.init!r},"
            f"repr={self.repr!r},"
            f"hash={self.hash!r},"
            f"compare={self.compare!r},"
            f"metadata={self.metadata!r},"
            f"kw_only={self.kw_only!r},"
            f"_field_type={self._field_type},"  # type: ignore
            f"reference={self.reference},"
            f"convert={self.convert},"
            f"validate={self.validate},"
            f"groups={self.groups},"
            ")"
        )


def fields(class_or_instance) -> Tuple[HydraletteField]:
    return dc_fields(class_or_instance)  # type: ignore
