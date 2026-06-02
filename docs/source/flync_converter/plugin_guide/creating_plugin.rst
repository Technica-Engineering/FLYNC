Creating a Plugin
=================

Overview
--------

Plugins in FLYNC extend functionality through converters. The recommended way to create a plugin is to extend the ``BaseConverter`` class and register it using the ``@hookimpl`` decorator.

Step-by-Step Guide
------------------

1. Extend BaseConverter and give it a name
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create a class that inherits from ``BaseConverter`` and has the name attribute already defined:

.. code-block:: python

   from flync.model import FLYNCModel
   from flync_converter.base.base_converter import BaseConverter

   class MyConverter(BaseConverter):
       name = "my_format"

       def can_decode(self):
           # should contain logic to scan the configured location
           # and figure out if decoding is possible or not
           return True

.. important::

   Please make sure to specify the converter name. This will be the name used to register the converter in the full map and choose it later, so this needs to be a unique identifier.

2. Follow the Constructor Signature
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Your converter **must not override** ``__init__`` unless it calls ``super().__init__(config)`` with the same signature:

.. code-block:: python

   from typing import Optional
   from flync_converter.base import BaseConverter, ConverterConfig

   class MyConverter(BaseConverter):
       name = "my_format"

       def __init__(self, config: Optional[ConverterConfig] = None):
           super().__init__(config)
           # your additional init here

The toolchain registers converters by calling ``register_converters()`` with no arguments (i.e. ``MyConverter()``), so the instance enters the registry with ``config = None``. The config is then injected at runtime just before ``encode()`` or ``decode()`` is called:

.. code-block:: python

   # What the toolchain does internally — you do not call this yourself
   converter = registry["my_format"]      # config is None here
   converter.config = ConverterConfig(config_path=str(destination))
   converter.encode(model)                # config is set here

This deferred-configuration pattern keeps all converters interchangeable. Because of it, your ``encode()`` and ``decode()`` implementations must guard against a missing config:

.. code-block:: python

   def encode(self, source):
       if self.config is None:
           raise ValueError("config must be set before encoding")
       # proceed with self.config.config_path ...

   def decode(self):
       if self.config is None:
           raise ValueError("config must be set before decoding")
       # proceed with self.config.config_path ...

3. Define a Custom Config (optional)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If your converter needs more than just a path, subclass ``ConverterConfig`` and annotate ``config`` on your class. The TUI will auto-detect the model and render all extra fields — plain types become text inputs, ``enum`` fields become dropdowns.

.. code-block:: python

   from enum import Enum
   from typing import Optional
   from flync_converter.base import ConverterConfig, BaseConverter

   class OutputFormat(Enum):
       CLASSIC = "classic"
       EXTENDED = "extended"

   class MyConverterConfig(ConverterConfig):
       output_format: OutputFormat = OutputFormat.CLASSIC
       indent: int = 2

   class MyConverter(BaseConverter):
       name = "my_format"
       config: MyConverterConfig  # tells the TUI which model to use

The TUI resolves the config model in this order:

1. A ``config`` class annotation (as above — recommended).
2. The ``config`` parameter annotation on ``__init__`` if you override it.
3. A ``config_model`` or ``Config`` class attribute set to the model class.

If none of these are present, the TUI falls back to the base ``ConverterConfig`` (single ``config_path`` field).

4. Implement Required Methods
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Implement the ``encode()`` and/or ``decode()`` methods depending on your plugin's purpose:

- **encode()**: Convert a FLYNCModel to your target format
- **decode()**: Parse your format and return a FLYNCModel

See the :ref:`JsonConverter example <jsonconverter-example>` for a complete implementation example.

5. Register Your Plugin
~~~~~~~~~~~~~~~~~~~~~~~~

Use the ``@hookimpl`` decorator to register your converter:

.. code-block:: python

   from flync_converter.registry import hookimpl

   @hookimpl
   def register_converters():
       return [MyConverter()]

6. Add entry point to package creation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use the entry point property of most Python package managers to define that your plugin belongs to the converters.

Example in ``pyproject.toml``:

.. code-block:: toml

   [project.entry-points."flync_converter"]
   my_format = "my_format.plugin"

Where the structure of your plugin would be as follows:

.. code-block:: text

   my_format/
   ├── pyproject.toml
   ├── README.md
   ├── src/
   │   └── my_format/
   │       ├── __init__.py
   │       └── plugin.py
   └── tests/
       └── test_plugin.py

Full Example
~~~~~~~~~~~~

Refer to the :doc:`examples` section for a complete, production-ready plugin implementation that demonstrates:

- Proper use of BaseConverter
- File I/O handling
- Error handling with validation
- Plugin registration

Adding a Built-in Converter
----------------------------

The steps above describe **external** plugins distributed as separate packages. If you are contributing a converter that ships *inside* ``flync_converter`` itself (e.g. a new format in ``src/flync_converter/converters/``), one extra step is required: you must also register the module in ``ConverterFactoryRegistry.load_builtin`` inside ``registry.py``.

.. code-block:: python

   # src/flync_converter/registry.py
   def load_builtin(self):
       from .converters import dbc_converter, flync_converter, json_converter, my_converter, yaml_converter

       for mod in (json_converter, yaml_converter, flync_converter, dbc_converter, my_converter):
           ...

Without this, the converter class and its ``register_converters`` hook exist but are never loaded, so it will not appear in the registry or the interactive TUI.

.. warning::

   Forgetting to add the module to ``load_builtin`` is a common pitfall. External plugins are discovered automatically via entry points; built-in converters are not — they must be listed explicitly.
