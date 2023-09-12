import logging
from dataclasses import MISSING, Field
from dataclasses import fields as dc_fields
from typing import Any, Callable, Dict, Optional, Tuple, Type

log = logging.getLogger(__name__)


def field(
    *,
    reference: Optional[Callable] = None,
    convert: Optional[Callable] = None,
    validate: Optional[Callable] = None,
    groups: Dict[str, type] = {},
    from_signature: Optional[Callable] = None,
    default=MISSING,
    default_factory=MISSING,
    init=True,
    repr=True,
    hash=None,
    compare=True,
    metadata=None,
    kw_only=MISSING,
) -> Any:
    """Function to create `HydraletteField`s. Like `dataclasses.field` with additional features.

    Args:
        reference (Optional[Callable], optional): Reference lambda that gets the root config and returns a value for this field. Defaults to None.
        convert (Optional[Callable], optional): Conversion lambda that gets the value passed via CLI and returns a value for this field. Defaults to None.
        validate (Optional[Callable], optional): Validation lambda that gets the value of this field and returns true if the value is valid. Defaults to None.
        groups (Dict[str, type], optional): Group definition, allows switching the config class of a sub-config field via cli. Defaults to {}.
        from_signature (Optional[Callable], optional): Use the signature of an arbitrary callable as the config class for this field. Defaults to None.
        default (_type_, optional): passed to `dataclasses.Field`. Defaults to MISSING.
        default_factory (_type_, optional): passed to `dataclasses.Field`. Defaults to MISSING.
        init (bool, optional): passed to `dataclasses.Field`. Defaults to True.
        repr (bool, optional): passed to `dataclasses.Field`. Defaults to True.
        hash (_type_, optional): passed to `dataclasses.Field`. Defaults to None.
        compare (bool, optional): passed to `dataclasses.Field`. Defaults to True.
        metadata (_type_, optional): passed to `dataclasses.Field`. Defaults to None.
        kw_only (_type_, optional): passed to `dataclasses.Field`. Defaults to MISSING.

    Returns:
        field (HydraletteField): Instantiated field
    """
    if from_signature is not None:
        if default_factory is not MISSING:
            log.warn("'from_signature' and 'default_factory' are not compatible.")
        if default is not MISSING:
            log.warn("'from_signature' and 'default' are not compatible.")

        return HydraletteField.from_signature(
            from_signature,
            field_kwargs=dict(
                reference=reference,
                convert=convert,
                validate=validate,
                groups=groups,
                init=init,
                repr=repr,
                hash=hash,
                compare=compare,
                metadata=metadata,
                kw_only=kw_only,
            ),
        )

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
        """HydraletteField constructor

        Args:
            reference (Optional[Callable], optional): see `hydralette.field`. Defaults to None.
            convert (Optional[Callable], optional): see `hydralette.field`. Defaults to None.
            validate (Optional[Callable], optional): see `hydralette.field`. Defaults to None.
            groups (Dict[str, type], optional): see `hydralette.field`. Defaults to {}.
            **kwargs (Any): passed to `dataclasses.Field.__init__`. Defaults to {}
        """
        super().__init__(**kwargs)
        self.reference = reference
        self.convert = convert
        self.validate = validate
        self.groups = groups

    @classmethod
    def from_dc_field(cls: Type["HydraletteField"], field: Field) -> "HydraletteField":
        """Convert `dataclass.Field` to `HydraletteField`.

        Args:
            field (Field): original field

        Returns:
            HydraletteField: adapted field
        """
        hydralette_field = cls(
            default=field.default,
            default_factory=field.default_factory,
            init=field.init,
            repr=field.repr,
            hash=field.hash,
            compare=field.compare,
            metadata=field.metadata,
            kw_only=field.kw_only,  # type: ignore
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
            f"kw_only={self.kw_only!r},"  # type: ignore
            f"_field_type={self._field_type},"  # type: ignore
            f"reference={self.reference},"
            f"convert={self.convert},"
            f"validate={self.validate},"
            f"groups={self.groups},"
            ")"
        )

    @staticmethod
    def from_signature(callable: Callable, field_kwargs: dict = {}) -> Any:
        """Generate field from signature. Called by `hydralette.field` if `from_signature` is not `None`.

        Args:
            callable (Callable): _description_
            field_kwargs (dict, optional): _description_. Defaults to {}.

        Returns:
            Any: _description_
        """
        from hydralette.config import (  # noqa: avoid circular import
            config_from_signature,
        )

        T = config_from_signature(callable)
        default_factory = lambda: T()
        T_field = field(default_factory=default_factory, **field_kwargs)
        T_field.type = T
        return T_field


def fields(class_or_instance) -> Tuple[HydraletteField]:
    """Wrapper around `dataclasses.fields` to change type hint to `Tuple[HydraletteField]`.

    Args:
        class_or_instance (_type_): _description_

    Returns:
        Tuple[HydraletteField]: _description_
    """
    return dc_fields(class_or_instance)  # type: ignore
