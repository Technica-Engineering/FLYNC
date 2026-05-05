import types
import typing

import flync  # noqa: F401  -- imports every model module, populating __subclasses__
from flync.core.base_models import FLYNCBaseModel


def _all_subclasses(cls: type) -> set[type]:
    seen: set[type] = set()
    stack = list(cls.__subclasses__())
    while stack:
        sub = stack.pop()
        if sub in seen:
            continue
        seen.add(sub)
        stack.extend(sub.__subclasses__())
    return seen


def _annotation_accepts_none(annotation: object) -> bool:
    origin = typing.get_origin(annotation)
    if origin is typing.Union or origin is types.UnionType:
        return type(None) in typing.get_args(annotation)
    return annotation is type(None)


class TestOptionalFieldDefaults:

    def test_nullable_fields_must_declare_a_default(self):
        """Pydantic v2: Optional[X] only widens the type to allow None; it does
        not make the field non-required. Any field whose annotation accepts
        None must declare an explicit default (typically None) — otherwise
        instantiation fails with ``Field required`` even though callers and
        docstrings treat the field as optional."""

        offenders: list[str] = []
        for model_cls in _all_subclasses(FLYNCBaseModel):
            if not model_cls.__module__.startswith("flync."):
                continue
            for field_name, field_info in model_cls.model_fields.items():
                if _annotation_accepts_none(field_info.annotation) and field_info.is_required():
                    offenders.append(f"{model_cls.__module__}.{model_cls.__name__}.{field_name}")

        assert not offenders, (
            "Fields whose annotation accepts None must declare a default "
            "(e.g. ``default=None``); otherwise Pydantic still treats them as "
            "required:\n  - " + "\n  - ".join(sorted(offenders))
        )
