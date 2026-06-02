Local Development & Debugging
=============================

When developing a plugin, registering via entry points requires your package to be fully installed (e.g. ``pip install -e .``). For quick iteration and debugging you can bypass this by registering your plugin module directly with the plugin manager.

Registering Without an Installed Package
-----------------------------------------

The plugin manager (``pm``) is accessible from ``flync_converter.registry``. Calling ``pm.register()`` on your module and then ``registry.load_plugins()`` is equivalent to what entry points do at runtime — but without the package installation step.

.. code-block:: python

   from flync_converter.registry import pm, registry
   import my_format.plugin as my_plugin

   # Register the plugin module directly
   pm.register(my_plugin)

   # Load all converters (built-ins + anything registered above)
   registry.load_plugins()

After this your converter is available in the registry like any installed plugin:

.. code-block:: python

   from flync_converter.registry import registry

   converter = registry["my_format"]

Example: Iterative Development Script
--------------------------------------

.. code-block:: python

   # dev_test.py — run from your plugin repo root
   from flync_converter.registry import pm, registry
   import src.my_format.plugin as my_plugin

   pm.register(my_plugin)
   registry.load_plugins()

   print("Registered converters:", list(registry.keys()))

   # Exercise your converter directly
   from flync_converter import convert
   convert("input.flync", "output.my_format", destination_type="my_format")

Example: Registering in Tests
------------------------------

Use the same approach in your test suite so tests run without requiring the package to be installed as a distribution:

.. code-block:: python

   # tests/conftest.py
   import pytest
   from flync_converter.registry import pm, registry
   import my_format.plugin as my_plugin

   @pytest.fixture(autouse=True)
   def register_plugin():
       if not pm.is_registered(my_plugin):
           pm.register(my_plugin)
       registry.load_plugins()

.. note::

   ``pm.is_registered()`` guards against double-registration if ``load_plugins()`` is called multiple times across tests.

How the Plugin Module Must Look
--------------------------------

The module you pass to ``pm.register()`` must expose a ``register_converters`` function decorated with ``@hookspec`` (same as when using entry points):

.. code-block:: python

   # my_format/plugin.py
   from flync_converter.base import BaseConverter
   from flync_converter.hookspec import hookspec

   class MyConverter(BaseConverter):
       name = "my_format"

       def can_decode(self):
           return True

       def encode(self, source):
           ...

       def decode(self):
           ...

   @hookspec
   def register_converters():
       return [MyConverter()]

This is the same structure required for production — so your dev registration and your production entry point use identical code.

When to Switch to Entry Points
-------------------------------

Once your plugin is ready for distribution or integration testing, switch to the standard entry point approach described in :doc:`creating_plugin`. The direct registration method is intended for local development only.
