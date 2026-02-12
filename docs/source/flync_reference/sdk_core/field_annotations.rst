.. _field_annotations:

Field Annotations
*******************

The annotations control how a field is loaded, generated or derived from external data.
They are expressed directly on the dataclass / pydantic model attributes.


Overview
--------

In *FLYNC* a field can stray away from standard yaml serializiation by being:

* **External** - the value is read from or written to a separate file / folder.
* **Implied** - the value is not stored but calculated on the fly using a defined strategy.

Both concepts are implemented by the ``External`` and ``Implied`` dataclasses.  The behaviour of
these dataclasses is further refined by three ``IntEnum`` strategy classes:

* ``NamingStrategy`` - how the external file / folder is named.
* ``OutputStrategy`` - how the external representation is organised (single file vs folder).
* ``ImpliedStrategy`` - how an implied field is calculated.

Using ``External`` in a model
-----------------------------

.. code-block:: python

    from flync.core.base_models import External, NamingStrategy, OutputStrategy
    from flync.model.base_model import FLYNCBaseModel

    class FLYNCGeneralConfig(FLYNCBaseModel):
        someip_config: Annotated[
                Optional[SOMEIPConfig],
                External(
                    output_structure=OutputStrategy.FOLDER,
                    naming_strategy=NamingStrategy.FIXED_PATH,
                    path="someip",
                ),
            ] = Field(
                default=None,
                description="contains the SOME/IP config for the entire system.",
            )


* ``path`` - location of the external resource relative to the current component, if left empty, this will be calculated from the naming_strategy attribute.
* ``output_structure`` - ``SINGLE_FILE`` creates one file, ``FOLDER`` creates a directory
  containing multiple files.
* ``naming_strategy`` - ``FIXED_PATH`` uses the explicit ``path``; ``AUTO`` would derive the
  name from the field name.

Using ``Implied`` in a model
----------------------------

.. code-block:: python

    from flync.core.base_models import Implied, ImpliedStrategy
    from flync.model.base_model import BaseModel

    class ECU(FLYNCBaseModel, UniqueName):
        name: Annotated[
            str,
            Implied(strategy=ImpliedStrategy.FOLDER_NAME)
        ] = pydantic.Field()


When the model is instantiated, *flync* will compute ``name`` based on the folder name
that contains the ECU definition.

Combining both annotations
--------------------------

A field can be declared as either ``External`` **or** ``Implied`` - they are mutually exclusive.
If both are needed, split the logic into separate helper properties.

Example model
~~~~~~~~~~~~~

.. code-block:: python

    from pathlib import Path
    from flync.core.base_models import External, Implied, NamingStrategy, OutputStrategy, ImpliedStrategy
    from flync.model.base_model import BaseModel

    class ECU(FLYNCBaseModel, UniqueName):
        name: Annotated[str, Implied(ImpliedStrategy.FOLDER_NAME)]
        ports: Annotated[List["ECUPort"], External()] = pydantic.Field(min_length=1)
        controllers: Annotated[List["Controller"], External()] = pydantic.Field()
        switches: Annotated[Optional[List["Switch"]], External()] = pydantic.Field(
            default=[]
        )
        topology: Annotated[
            "InternalTopology",
            External(),
        ] = pydantic.Field()
        info: Annotated[
            "MetadataECU",
            External(
                output_structure=OutputStrategy.SINGLE_FILE,
            ),
        ] = pydantic.Field()

Key points
----------

* Choose the appropriate ``NamingStrategy`` to control file naming.
* Use ``OutputStrategy.FOLDER`` when a field naturally maps to multiple files (e.g. controllers).
* ``ImpliedStrategy.FOLDER_NAME`` is handy for identifiers that follow the directory layout.
* ``ImpliedStrategy.FILE_NAME`` handy for identifiers that are derived from the field value as a file name.
* All strategy classes are defined in ``src/flync/core/annotations`` - keep them imported from that module
  to avoid circular imports.
