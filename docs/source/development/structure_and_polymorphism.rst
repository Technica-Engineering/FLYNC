.. _structure_and_polymorphism:

************************
Structure & polymorphism
************************

How a field becomes a file
==========================

Three annotations from ``flync.core.annotations`` (``External``, ``Implied``, ``Reference``)
decouple the model from the repository layout: they tell the loader where a value comes from and
the generator where it goes. The directory tree they produce is the one config authors see,
documented at :ref:`writing_flync_config` — read the two together when you change an annotation,
because changing one changes the other.

.. list-table::
   :header-rows: 1

   * - Annotation
     - Meaning
     - Typical use
   * - ``External``
     - value lives in a separate file or folder
     - ``List``/nested-model fields split across the config repo
   * - ``Implied``
     - value is derived, not stored
     - an object's ``name`` taken from its folder name
   * - ``Reference``
     - value is a key naming an object loaded elsewhere
     - connections referring to a port/controller by name

``External`` — one field, one place
-----------------------------------

.. code-block:: python

    from typing import Annotated

    from flync.core.annotations import External, NamingStrategy, OutputStrategy

    ecus: Annotated[
        list[ECU],
        External(output_structure=OutputStrategy.FOLDER, naming_strategy=NamingStrategy.FIELD_NAME),
    ] = Field()

    metadata: Annotated[
        SystemMetadata,
        External(
            output_structure=OutputStrategy.SINGLE_FILE | OutputStrategy.OMMIT_ROOT,
            naming_strategy=NamingStrategy.FIXED_PATH,
            path="system_metadata",
        ),
    ]

Strategies combine with ``|``: ``SINGLE_FILE`` writes one ``<field>.flync.yaml``, ``FOLDER`` writes a
directory, ``OMMIT_ROOT`` suppresses the wrapper key, ``FIXED_PATH`` fixes the name instead of
deriving it from the field. ``FIXED_ROOT`` together with ``External(root=...)`` re-bases the
path on a directory other than the parent's. The full behaviour is in :ref:`field_annotations`.

``Implied`` — the name is the folder
------------------------------------

.. code-block:: python

    from flync.core.annotations import Implied, ImpliedStrategy

    name: Annotated[str, Implied(strategy=ImpliedStrategy.FOLDER_NAME)] = Field()

``Reference`` — a key plus the object it resolves to
----------------------------------------------------

.. code-block:: python

    class ECUPortToXConnection(InternalConnection):
        ecu_port_name: Annotated[str, Reference(source="_ecu_port")] = Field(alias="ecu_port")

        _ecu_port: ECUPort | None = None    # wired during workspace resolution

        @property
        def ecu_port(self) -> ECUPort:
            return self._ecu_port

The public field is the *string* that appears in YAML (hence ``alias``); the named private
attribute holds the resolved object. When the field is not a plain name but a composite key, add a
``field_serializer`` so dumps write the key back, as
:class:`~flync.model.flync_4_someip.deployment.SOMEIPServiceDeployment` does for its ``service`` id.

Discriminated unions
====================

Polymorphic fields never probe dicts — each variant carries a ``Literal`` tag with a default, and
the field points the union at that tag.

**1 — the tag field** (``mode``, ``type`` or ``deployment_type`` by domain):

.. code-block:: python

    class BASET1(FLYNCBaseModel):
        mode: Literal["base_t1"] = Field(default="base_t1")
        ...

    class MII(FLYNCBaseModel):
        type: Literal["mii"] = Field(default="mii")
        ...

**2 — the union field** declares the discriminator:

.. code-block:: python

    class ECUPort(FLYNCBaseModel):
        mdi_config: BASET1 | BASET1S | BASET = Field(default_factory=BASET1, discriminator="mode")
        mii_config: MII | RMII | SGMII | RGMII | XFI | None = Field(default=None, discriminator="type")

For a list whose *items* are a discriminated union, attach the ``Field`` to the element
annotation (as ``CANBus.frames`` does):

.. code-block:: python

    frames: list[Annotated[CANFrame | CANFDFrame, Field(discriminator="type")]] = Field(default_factory=list)

**3 — list items of mixed variants** get a thin ``RootModel`` wrapper that renders as the bare
mapping in YAML:

.. code-block:: python

    class DeploymentUnion(RootModel):
        root: (
            SOMEIPServiceConsumer
            | SOMEIPServiceProvider
            | SOMEIPSDDeployment
            | PDUSender
            | PDUReceiver
            | PDUForwarder
            | DoIPServerDeployment
            | DoIPDiscoveryDeployment
        ) = Field(discriminator="deployment_type")

Variants that share behaviour hang off an abstract base, which keeps the common fields and the
tag type honest:

.. code-block:: python

    class SOMEIPServiceDeployment(abc.ABC, FLYNCBaseModel):
        deployment_type: DeploymentTypes
        service: int = Field(gt=0, lt=0xFFFF, strict=True)
        ...

    class SOMEIPServiceConsumer(SOMEIPServiceDeployment):
        deployment_type: Literal["someip_consumer"] = Field(default="someip_consumer")

When adding variants
--------------------

* The tag must be ``Literal``, **and** it must have a default. The two halves matter for
  different reasons, and conflating them makes a missing ``type:`` line hard to debug:

  - ``flync.sdk.utils.model_dependencies`` collects a model's discriminator fields by testing
    ``get_origin(annotation) is Literal`` — the annotation alone. A tag annotated as plain
    ``str`` is invisible to the dependency graph.
  - ``flync.sdk.utils.model_dumper`` then adds those names to ``model_fields_set`` before
    dumping, which is what stops pydantic from dropping a tag the YAML never set explicitly.
    Without the default there is nothing to write back.
* Keep the tag spelled like the class (``"someip_consumer"`` for ``SOMEIPServiceConsumer``);
  loaders and factory helpers resolve it by value.
* Add each variant to the model docstring's type list so the YAML schema docs stay complete.
