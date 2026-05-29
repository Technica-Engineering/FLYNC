"""Utilities for dumping FLYNC models with discriminator fields included."""

from pydantic import BaseModel


def dump_model_with_discriminators(model: BaseModel, **kwargs) -> dict:
    """
    Dump a model to a dictionary, ensuring Literal discriminator fields are included.

    When a model has Literal-typed discriminator fields with default values, Pydantic
    may exclude them from the dump if they weren't explicitly set during model creation.
    This function ensures they are included in the output by looking up discriminator info
    from the ModelDependencyGraph (built once at startup) and marking them as set before
    dumping.

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
        node_info = graph.fields_info.get(model.__class__.__name__)
        if node_info and node_info.discriminator_fields:
            model.model_fields_set.update(node_info.discriminator_fields)
    except Exception:
        # Graph not available or model not in graph, skip marking
        pass

    return model.model_dump(**kwargs)
