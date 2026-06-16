"""Utilities for dumping FLYNC models with discriminator fields included."""

from pydantic import BaseModel


def dump_model_with_discriminators(model: BaseModel, **kwargs) -> dict:  # NOSONAR python:S3776
    """
    Dump a model to a dictionary, ensuring Literal discriminator fields are included.

    When a model has Literal-typed discriminator fields with default values, Pydantic
    may exclude them from the dump if they weren't explicitly set during model creation.
    This function ensures they are included in the output by looking up discriminator info
    from the ModelDependencyGraph (built once at startup) and marking them as set before
    dumping. Recursively applies this to all nested models.

    Uses the pre-built ModelDependencyGraph for O(1) lookup efficiency. Falls back to no-op
    if the graph is not available (e.g., during early initialization).

    Args:
        model: The Pydantic model instance to dump.
        **kwargs: Additional arguments to pass to model.model_dump().

    Returns:
        dict: The dumped model data with discriminators included.
    """
    try:
        from flync.model import FLYNCModel
        from flync.sdk.utils.model_dependencies import get_model_dependency_graph

        graph = get_model_dependency_graph(FLYNCModel)

        def mark_discriminators_recursive(m: BaseModel):
            """Recursively mark discriminator fields as set for this model and all nested models."""
            if not isinstance(m, BaseModel):
                return

            node_info = graph.fields_info.get(m.__class__.__name__)
            if node_info and node_info.discriminator_fields:
                m.model_fields_set.update(node_info.discriminator_fields)

            # Recursively process nested models
            for field_name in type(m).model_fields:
                try:
                    field_value = getattr(m, field_name, None)
                    if isinstance(field_value, BaseModel):
                        mark_discriminators_recursive(field_value)
                    elif isinstance(field_value, list):
                        for item in field_value:
                            if isinstance(item, BaseModel):
                                mark_discriminators_recursive(item)
                    elif isinstance(field_value, dict):
                        for v in field_value.values():
                            if isinstance(v, BaseModel):
                                mark_discriminators_recursive(v)
                except Exception:
                    pass

        mark_discriminators_recursive(model)
    except Exception:
        # Graph not available or model not in graph, skip marking
        pass
    kwargs.setdefault("mode", "json")
    return model.model_dump(**kwargs)
