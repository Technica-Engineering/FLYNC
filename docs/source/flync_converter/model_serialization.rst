Model Serialization
===================

Overview
--------

When serializing FLYNC models to YAML, JSON, or other formats, certain Literal-typed discriminator fields may be excluded from the output if they have default values and were not explicitly set during model creation.

This guide explains how to properly dump FLYNC models to ensure discriminators are included in the serialized output.

The Problem
-----------

Pydantic v2 tracks which fields were explicitly set on a model instance via ``model_fields_set``. During serialization with ``model_dump()``, by default all fields are included. However, when custom logic excludes unset fields or when downstream code expects discriminators to be present, Literal fields with defaults may appear missing.

Example:

.. code-block:: python

    class LINMasterInterfaceConfig(FLYNCBaseModel):
        node_type: Literal["master"] = Field(default="master")  # Has default
        bus_ref: str = Field()

    # When created, node_type is not in model_fields_set:
    config = LINMasterInterfaceConfig(bus_ref="CAN1")
    # config.model_fields_set might not contain "node_type"


Solution: Use ``dump_model_with_discriminators``
-------------------------------------------------

The SDK provides a utility function that ensures discriminator fields are always included:

.. code-block:: python

    from flync.sdk.utils.model_dumper import dump_model_with_discriminators

    # Correct way to dump FLYNC models
    data = dump_model_with_discriminators(model)
    yaml.dump(data, output_file)


How It Works
^^^^^^^^^^^^

1. **Graph Lookup (O(1))**: Uses the pre-built ``ModelDependencyGraph`` (constructed once at startup) to identify which fields are discriminators
2. **Mark as Set**: Temporarily marks those fields in ``model_fields_set`` before dumping
3. **Safe Fallback**: If the graph is not available, silently skips marking (no error)

Performance
^^^^^^^^^^^

- **First call**: Slightly slower (initializes graph lookup if needed)
- **Subsequent calls**: O(1) lookup from cached graph, negligible overhead
- **Memory**: No additional memory per instance; uses shared graph


Usage in Converters
-------------------

All converters should use this utility when dumping models.

For FLYNCConverter
^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from flync.sdk.utils.model_dumper import dump_model_with_discriminators

    # In encode method:
    def encode(self, source: FLYNCModel):
        data = dump_model_with_discriminators(source, exclude=...)
        # ... write to files


For SDK Workspace
^^^^^^^^^^^^^^^^^

In ``flync_workspace.py``, replace:

.. code-block:: python

    # Old:
    content = flync_model.model_dump(exclude=exclude, exclude_unset=...)

    # New:
    content = dump_model_with_discriminators(
        flync_model,
        exclude=exclude,
        exclude_unset=...
    )


When to Use
-----------

- **Always use** when dumping models for output (files, APIs, serialization)
- **Skip** for internal operations that don't care about discriminators
- **Safe to use** everywhere—fallback behavior handles edge cases


Example
-------

.. code-block:: python

    from flync.sdk.utils.model_dumper import dump_model_with_discriminators
    from flync.model import FLYNCModel

    # Load or create a model
    model = FLYNCModel(...)

    # Dump with discriminators included
    output_dict = dump_model_with_discriminators(model)

    # Now discriminator fields are guaranteed to be in output_dict
    # even if they have default values


Architecture
------------

- **Core**: No changes. FLYNCBaseModel stays clean.
- **SDK**: Handles discriminator marking via ``dump_model_with_discriminators``
- **Graph**: Provides O(1) lookup of discriminator fields, computed once at startup

This design keeps the core model lightweight while leveraging SDK infrastructure for specialized output requirements.
