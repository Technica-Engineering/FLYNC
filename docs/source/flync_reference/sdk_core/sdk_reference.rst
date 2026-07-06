flync.sdk
##########

This page is a full reference of the SDK for developers and contributors to FLYNC.

.. _flync_workspace:

FLYNC Workspace
===================

.. autoclass:: flync.sdk.workspace.flync_workspace.FLYNCWorkspace
   :members:
   :undoc-members:

.. automodule:: flync.sdk.context.workspace_config
   :members:


Semantic Objects
=================

.. _semantic_object:

SemanticObject
---------------

.. autoclass:: flync.sdk.workspace.objects.SemanticObject
   :members:

.. _object_metadata:

ObjectMetadata
---------------

Provides lightweight metadata about semantic objects without exposing the full model.

.. autoclass:: flync.sdk.workspace.objects.ObjectMetadata
   :members:

**Usage Example:**

.. code-block:: python

    from flync.sdk.workspace.flync_workspace import FLYNCWorkspace
    from flync.sdk.workspace.ids import ObjectId

    workspace = FLYNCWorkspace.load_workspace("my_ws", "/path/to/workspace")

    # Get metadata (lightweight, no full model)
    metadata = workspace.get_metadata(ObjectId("ecus.my_ecu"))
    print(metadata.type_name)      # "ECU"
    print(metadata.fields)         # {"name": str, "description": str, ...}
    print(metadata.parent_id)      # "ecus"
    print(metadata.child_ids)      # ["ecus.my_ecu.controllers", ...]

    # Serialize to dict for JSON
    metadata_dict = metadata.to_dict()

    # Get full model only when needed
    semantic_obj = workspace.get_object(ObjectId("ecus.my_ecu"))
    model_data = semantic_obj.model.model_dump()


Document
=========

.. autoclass:: flync.sdk.workspace.document.Document
   :members:


Utils & Helpers
================
.. automodule:: flync.sdk.utils.field_utils
   :members:

.. automodule:: flync.sdk.helpers.generation_helpers
   :members:
