.. _flync_converter:

FLYNC Converters
================

A flexible converter library for transforming data formats with plugin support, using FLYNC as the common intermediate model.

Features
--------

- **Plugin-based architecture** - extend with custom converters via ``pluggy`` entry points
- **Multiple format support** - built-in JSON, YAML, and FLYNC converters
- **Interactive TUI** - full terminal UI (Textual) with auto-generated config forms
- **Scriptable CLI** - ``flync-converter convert`` for pipeline use
- **Type-safe** - Pydantic config models throughout

.. toctree::
   :maxdepth: 2
   :caption: Contents

   quick_start
   usage
   cli
   best_practices
   model_serialization
   common_usecases
   plugin_guide/index
