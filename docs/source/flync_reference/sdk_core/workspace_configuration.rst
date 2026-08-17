.. _workspace_configuration_reference:

############################
Workspace Configuration
############################

The ``WorkspaceConfiguration`` class controls how a FLYNC workspace is loaded, validated, and serialized. It defines file extensions, object mapping
behavior, serialization options, the root model, and version tracking.

A workspace can carry its own configuration on disk, in a ``.flync/config.yaml`` file at the workspace root. The workspace is then self-describing: it
is loaded the same way by every tool, and there is no need to rebuild the same ``WorkspaceConfiguration`` in a script each time the workspace is
opened.

Overview
========

Every workspace has a configuration that controls:

- **file extensions**: Which files are recognized as FLYNC configuration files
- **object mapping**: Whether the workspace maps all objects (performance tradeoff)
- **serialization**: How fields are excluded when unset
- **version**: FLYNC version used to create the configuration (tracking only, see below)

The ``root_model`` field is part of the configuration object but is deliberately **not**
part of the file. See :ref:`workspace_configuration_root_model`.

.. note::

	``version`` records the FLYNC release that last wrote the file, so future releases can migrate older
	configuration files. When a newer FLYNC rewrites a workspace the stamp moves forward, because the file
	is then in that newer release's format; it is never moved backwards. It is **not** checked when a
	configuration is loaded; no compatibility is enforced today.

Configuration File Format
=========================

**Convention:** ``.flync/config.yaml`` in the workspace root

.. code-block:: text

	myproject/
	  .flync/
	    config.yaml
	  my_ecu.flync.yaml

``.flync/`` is the single directory FLYNC tooling persists into, and is meant
to be committed alongside the workspace.

**File Structure:**

.. code-block:: yaml

	# Only non-default values are serialized
	version:
	  version_schema: pep440
	  version: |flync_version|

	exclude_unset: false
	map_objects: true
	allowed_extensions:
	  - .flync.yaml
	  - .flync.yml
	  - .safety.yaml

	list_objects_mode:
	  - INDEX
	  - NAME

**Auto-Discovery:**

When calling ``FLYNCWorkspace.load_workspace()`` without an explicit ``workspace_config`` parameter:

.. code-block:: python

	workspace = FLYNCWorkspace.load_workspace(
		workspace_name="myproject",
		workspace_path="/path/to/project"
		# .flync/config.yaml is auto-discovered from /path/to/project/
	)

If ``.flync/config.yaml`` exists, it's loaded. Otherwise, defaults are used.

.. _workspace_configuration_root_model:

The Root Model Is Not Configurable From File
============================================

``root_model`` is the only configuration field that is **programmatic-only**. It is set by
the host application in code (the SDK, the REST server, the language server, a script) and
is:

- **never written** to ``.flync/config.yaml``
- **rejected** when present in ``.flync/config.yaml``
- **rejected** when given as a module path string, e.g. ``WorkspaceConfiguration(root_model="my.module.MyModel")``

The reason is that resolving a class named in a file means importing it, which means
executing code that ships inside a workspace. FLYNC workspaces are exchanged between
suppliers and OEMs, so a workspace is treated strictly as data. Opening one never imports
anything from it and never modifies ``sys.path``.

A consequence is that a custom root model set in code is not restored when the workspace is
reopened; the loading application must supply it again:

.. code-block:: python

	config = WorkspaceConfiguration(root_model=MyRootModel)  # class, never a string
	workspace = FLYNCWorkspace.load_workspace("myproject", "/path/to/project", config)

Configuration Resolution Priority
=================================

When loading a workspace, configurations are resolved in this order (highest to lowest priority):

1. **Explicit config object** passed to ``load_workspace(workspace_config=config_obj)``
2. **Explicit config file path** (``str`` or ``Path``) passed to ``load_workspace(workspace_config="path/to/config.yaml")``
3. **Auto-discovered** ``.flync/config.yaml`` in workspace root
4. **Default** ``WorkspaceConfiguration()``

If an explicit config object is passed, both the file path and auto-discovered file are ignored.

Persisting Configuration
========================

Configuration is automatically saved when calling ``generate_configs()``:

.. code-block:: python

	workspace = FLYNCWorkspace.load_workspace("myproject", "/path/to/project")
	# ... modify workspace and models ...
	workspace.generate_configs()  # Persists configuration to .flync/config.yaml

To explicitly save without saving the full workspace:

.. code-block:: python

	workspace.save_workspace_config()  # Saves to workspace_root/.flync/config.yaml (creating .flync/ if needed)

**Suppressing the configuration file:**

Not every directory a workspace is written to should receive FLYNC tooling files. Generated or
converted output, scratch directories, and workspaces whose configuration file is maintained by
hand are all cases where the implicit write is unwanted. Set ``persist_config`` to opt out:

.. code-block:: python

	# For the lifetime of the workspace
	config = WorkspaceConfiguration(persist_config=False)
	workspace = FLYNCWorkspace.load_workspace("myproject", "/path/to/project", config)
	workspace.generate_configs()  # writes the FLYNC documents, no .flync/config.yaml

	# Or for a single call
	workspace.generate_configs(persist_config=False)

The per-call argument wins over the configuration field in both directions, so
``generate_configs(persist_config=True)`` forces the write even when the field is ``False``.

``persist_config`` governs only this implicit write. ``save_workspace_config()`` asks for the file
directly and always produces it, regardless of the flag. Because the field itself is persisted, a
workspace whose ``.flync/config.yaml`` contains ``persist_config: false`` keeps that file untouched
across saves - which is how a hand-maintained configuration file is protected from being rewritten.

**Default Exclusion:**

Only non-default values are serialized to YAML:

.. code-block:: yaml

	# Default values (not saved)
	exclude_unset: true
	map_objects: false
	persist_config: true
	list_objects_mode:
	  - INDEX
	  - NAME

	# Always saved (version is always included, stamped from the running FLYNC release)
	version:
	  version_schema: pep440
	  version: |flync_version|

Configuration Fields
====================

**flync_file_extension** (str)
  Primary file extension for FLYNC files. Default: ``.flync.yaml``

**allowed_extensions** (set[str])
  File extensions recognized as FLYNC files. Default: ``{".flync.yaml", ".flync.yml"}``

**exclude_unset** (bool)
  When ``True``, fields not explicitly set on models are omitted from serialized output. Default: ``True``

**root_model** (Type[FLYNCBaseModel])
  The Pydantic model class used to validate workspace contents. Set in code only: it is never serialized and cannot be read from a configuration file
  (see :ref:`workspace_configuration_root_model`). Default: ``FLYNCModel``

**map_objects** (bool)
  When ``True``, the workspace maps all objects (improves lookup speed but increases memory). Default: ``False``

**list_objects_mode** (ListObjectsMode)
  Controls how list items are keyed in workspace object map. Supports ``INDEX`` and/or ``NAME`` flags. Default: ``INDEX | NAME``

**persist_config** (bool)
  When ``True``, saving the whole workspace with ``generate_configs()`` also writes this configuration to ``.flync/config.yaml``. Set it to ``False``
  for output directories that should contain nothing but the generated FLYNC files, or to protect a hand-maintained configuration file from being
  rewritten. Only the implicit write is suppressed: ``save_workspace_config()`` always writes. Default: ``True``

**version** (BaseVersion)
  FLYNC release that last wrote this configuration. Auto-detects the installed version, falling back to ``0.0.0`` when the distribution metadata is
  unavailable. On save the stamp is advanced to the running release if that is newer than the recorded one, and left alone otherwise (including when
  the recorded version uses a different ``version_schema``, which makes the two incomparable). Default: current FLYNC version (PEP 440 format)

Error Handling
==============

**Programmatic-only field set in a file:**

.. code-block:: text

	ValueError: /path/to/.flync/config.yaml: root_model cannot be set from a configuration file.
	It is supplied by the host application in code so that opening a workspace never imports code it names.

**Unknown key (typo) in a file:**

.. code-block:: text

	ValidationError: 1 validation error for WorkspaceConfiguration
	map_object
	  Extra inputs are not permitted

**YAML file not found:**

.. code-block:: text

	FileNotFoundError: Configuration file not found: /path/to/.flync/config.yaml

**Invalid configuration format:**

.. code-block:: text

	ValidationError: 1 validation error for WorkspaceConfiguration
	version
	  Input should be a valid dictionary or instance of BaseVersion

API Reference
=============

.. autoclass:: flync.sdk.context.workspace_config.WorkspaceConfiguration
   :members:
   :undoc-members:

.. autoclass:: flync.sdk.context.workspace_config.ListObjectsMode
   :members:
   :undoc-members:


See Also
========

- :ref:`flync_workspace` - FLYNCWorkspace loading and management
