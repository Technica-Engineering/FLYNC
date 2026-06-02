Plugin Examples
===============

Creating a Custom Converter
----------------------------

.. _jsonconverter-example:

JsonConverter Example
~~~~~~~~~~~~~~~~~~~~~

The following example demonstrates how to create a custom converter plugin using the project's ``BaseConverter`` class. This example shows the JSON converter implementation:

.. code-block:: python

   import json
   import os
   from pathlib import Path

   from flync.model import FLYNCModel
   from flync_converter.base.base_converter import BaseConverter
   from flync_converter.registry import hookimpl
   from flync_converter.converters.helpers import pydantic_dump


   class JsonConverter(BaseConverter):
       """Convert between FLYNC models and JSON format."""

       name = "json"

       def can_decode(self):
           """Indicate that this converter can decode JSON files."""
           return True

       def encode(self, source: FLYNCModel):
           """Encode a FLYNCModel to a JSON file."""
           output_path = os.path.join(
               self.config.config_path, source.__class__.__name__ + ".json"
           )
           Path(output_path).parent.mkdir(parents=True, exist_ok=True)
           with open(output_path, "w", encoding="utf-8") as output:
               json.dump(pydantic_dump(source), output, indent=2, sort_keys=False)

       def decode(self) -> FLYNCModel:
           """Decode JSON files from config path into a FLYNCModel."""
           dict_content = {}
           root = Path(self.config.config_path)

           for json_file in root.rglob("*.json"):
               with json_file.open("r", encoding="utf-8") as f:
                   data = json.load(f)
                   if isinstance(data, dict):
                       dict_content.update(data)

           return FLYNCModel.model_validate(dict_content)


   @hookimpl
   def register_converters():
       """Register this converter plugin."""
       return [JsonConverter()]

**Key Points:**

- Extends ``BaseConverter`` base class
- Implements ``encode()`` to serialize FLYNCModel to JSON
- Implements ``decode()`` to parse JSON files back to FLYNCModel
- Uses ``@hookimpl`` decorator to register the converter
- Supports recursive JSON file loading and merging
