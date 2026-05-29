Plugin Development Guide
========================

Learn how to extend FLYNC with custom converters and transformations.

Overview
--------

The plugin system is built around:

- Create custom format converters (especially useful for complex and/or external data formats like ARXML)
- Extend core functionality

Plugin Architecture
-------------------

Each plugin is a self-contained module that implements the converter interface. Plugins follow a standard structure and lifecycle:

1. **Initialization**: Plugin is loaded and configured
2. **Registration**: Plugin registers its capabilities
3. **Execution**: Plugin processes data during conversion
4. **Cleanup**: Resources are released after use

.. toctree::
   :maxdepth: 2
   :caption: Plugin Guide

   introduction
   creating_plugin
   examples
   local_development
