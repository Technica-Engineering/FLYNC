.. _model_patterns:

**************
Model patterns
**************

The base class
==============

Every model extends :class:`~flync.core.base_models.base_model.FLYNCBaseModel`. It already sets
``extra="forbid"``, ``validate_by_name=True`` and ``validate_assignment=True``, and overrides
``model_dump`` to drop ``None`` values and dump aliases — so do not re-declare the config
and do not pass ``exclude_none``/``by_alias`` at every call site.

.. code-block:: python

    from typing import Literal

    from pydantic import Field

    from flync.core.base_models import FLYNCBaseModel


    class BASET1(FLYNCBaseModel):
        """..."""

        mode: Literal["base_t1"] = Field(default="base_t1")
        speed: Literal[100, 1000] = Field(default=100)
        duplex: Literal["full"] = Field(default="full")
        role: Literal["master", "slave"] = Field(default="slave")
        autonegotiation: bool = Field(default=False)

A polymorphic family may instead inherit from an abstract base (``class X(abc.ABC, FLYNCBaseModel)``)
that declares the shared fields and the tag — see :class:`~flync.model.flync_4_someip.deployment.SOMEIPServiceDeployment`.

Fields
======

The shapes below are written in the current conventions rather than copied from source — the
tree still carries older spellings of the same declarations (see `Typing rules`_).

.. code-block:: python

    name: str = Field()                                        # required
    description: str | None = Field(default=None)              # optional, immutable default
    frames: list[CANFrame] = Field(default_factory=list)       # optional, mutable default
    service: int = Field(gt=0, lt=0xFFFF, strict=True)         # constrained scalar
    multicast_groups: list[MulticastGroupMembership] = Field(default_factory=list, exclude=True)

* Use ``strict=True`` on integer ids and protocol values so a YAML string is an error, not a coercion.
* Put range constraints (``gt`` / ``ge`` / ``lt`` / ``le``) on the ``Field`` — not in a hand-written validator.
* ``exclude=True`` keeps internally derived fields (populated after load) out of the dumped YAML.

The live counterparts are worth reading next to them: ``multicast_groups`` in
``flync_4_ecu/ecu.py``, the constrained ``service`` id in ``flync_4_someip/deployment.py`` (which
also carries a ``Reference`` annotation), and ``CANBus.frames`` in ``flync_4_bus/can_bus.py``,
whose element type is a discriminated union — see :ref:`structure_and_polymorphism`.

Docstrings are the API reference
================================

The Sphinx API docs and the model reference are generated from the class docstring, so every
field the class itself declares needs an entry in its NumPy-style ``Parameters`` section — name,
type, and a statement of the default where it has one. Inherited fields stay documented on the
base class. Refer to other models with fully-qualified :class: roles.

The example below is the real docstring of
:class:`~flync.model.flync_4_ecu.phy.BASET1` (``src/flync/model/flync_4_ecu/phy.py``):

.. code-block:: python

    class BASET1(FLYNCBaseModel):
        """
        Represents a BASE-T1 Ethernet interface configuration.

        Parameters
        ----------
        mode : Literal["base_t1"]
            Interface mode. Defaults to ``"base_t1"``.

        speed : int
            Supported link speed in megabits per second. Valid values are 100 or 1000.

        duplex : Literal["full"]
            Duplex mode. Defaults to ``"full"``.

        role : Literal["master", "slave"]
            Role of the PHY, either master or slave.

        autonegotiation : bool, optional
            Indicates whether autonegotiation is enabled (defaults to ``False``).
        """

How the default is stated
-------------------------

Either form satisfies the gate: the ``", optional"`` suffix on the type line, or the word
*default* in the description (for example "Defaults to ``False``."). Two kinds of default need no
statement at all:

* a ``default_factory`` — ``list of X`` already says the field may be omitted;
* a ``Literal``-annotated default — the documented type spells out the only legal value, which
  is why ``mode``, ``duplex`` and ``role`` above carry no ``", optional"``.

``scripts/ci/check_model_docstrings.py`` is the gate. It reports five kinds of finding:
``missing`` (an undocumented field), ``unknown`` (a documented non-field), ``type`` (documented
type disagrees with the annotation), ``optional`` (the default statement disagrees with the
field), and ``bounds`` (a ``Field`` constraint the description never mentions). Its module
docstring carries the authoritative template.

Private attributes
==================

A leading-underscore, *annotated* class attribute is already a private attribute in Pydantic v2:
it is excluded from ``model_fields`` and ``model_dump``, and copied by ``model_copy``.

.. code-block:: python

    # ✔ the convention
    _service_ref: SOMEIPServiceInterface | None = None
    _state_effective_members: list[EffectiveMember] = []

    # ✘ do not write this — the PrivateAttr default never matches the Optional[T] annotation
    _service_ref: Optional[SOMEIPServiceInterface] = PrivateAttr(default=None)

Private attributes hold back-references wired in during workspace resolution (paired with a
``Reference`` annotation — see :ref:`structure_and_polymorphism`) and derived caches. Expose them
through read-only ``@property`` accessors rather than making them public.

.. code-block:: python

    _ecu: ECU | None = None

    @property
    def ecu(self) -> ECU | None:
        return self._ecu

Some classes carry a ``_type`` tag this way because the workspace binding code reads
``obj.type`` through a property. That is fine — the tag is a private attribute like any other:

.. code-block:: python

    _type: Literal["ecu_port"] = "ecu_port"

    @property
    def type(self) -> str:
        return self._type

Typing rules
============

Two conventions, two different enforcers — they are often quoted as one rule, and are not.

PEP 604 unions
--------------

Write ``X | Y`` and ``X | None`` rather than ``typing.Union`` / ``typing.Optional``; SonarQube
rule ``S6546`` reports the legacy spellings.

.. code-block:: python

    def find_ecu(self) -> ECU | None: ...        # ✔
    def find_ecu(self) -> Optional[ECU]: ...     # ✘

.. note::
   This is the rule for **new and touched** code — it does not describe the tree as it stands.
   ``src/`` still holds several hundred ``Optional[...]`` / ``List[...]`` annotations predating
   the convention, so do not read the surrounding code as the example. Equally, do not convert
   unrelated files while you are in there: a typing sweep is its own change.

``Optional[...]`` stays the only legal spelling where the inner name must remain quoted — see
the ``TYPE_CHECKING`` case below.

Quoted annotations
------------------

``scripts/ci/check_lazy_typing.py`` runs as a pre-commit hook and as a CI gate. It has no opinion
on ``Union``/``Optional``; it fails on exactly three findings:

**1 —** ``redundant``: do not quote an annotation whose names are already in scope.

.. code-block:: python

    def locator(self, controller: Controller, socket: Socket) -> str: ...   # ✔
    def locator(self, controller: "Controller", socket: "Socket") -> str: ...  # ✘ redundant

**2 —** ``whole-quote``: quote only the genuinely-unbound name, never the whole expression.

.. code-block:: python

    def _collect(self, model: "FLYNCModel") -> list[str]: ...   # ✔ forward/cyclic reference
    def _collect(self, model: "FLYNCModel") -> "list[str]": ... # ✘ whole-quote

**3 —** ``self-return``: a method returning its own class name in quotes — use ``typing.Self``
instead, see `Self-typed methods`_.

For a *private* attribute whose type is only imported under ``if TYPE_CHECKING:`` the name is not
bound at runtime, so it must stay quoted — but only the name: ``"EthernetMultidropNode" | None``
is invalid syntax, hence ``Optional["EthernetMultidropNode"]`` remains legal there.

For the rare unavoidable exception, put ``# lazy-typing: allow`` on the annotation's line.

Self-typed methods
==================

``mode="after"`` validators take ``self`` and return the model — annotate ``-> Self``
(``from typing import Self``); never the enclosing class name in quotes.

.. code-block:: python

    from typing import Self

    from pydantic import model_validator

    class ECUPort(FLYNCBaseModel):
        ...

        @model_validator(mode="after")
        def verify_mdi_and_mii_config_have_same_speed(self) -> Self:
            ...
            return self
