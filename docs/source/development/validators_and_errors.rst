.. _validators_and_errors:

*******************
Validators & errors
*******************

Which validator, in which place
===============================

Reach for the cheapest mechanism that expresses the rule:

1. **Constraints on the Field** — ranges, ``strict``, lengths. Not a validator at all; see :ref:`model_patterns`.
2. **Annotated validators** — per-value rules, reusable across models. Put them in
   ``flync.core.validators`` or ``flync.core.datatypes`` and reference them from the annotation:

   .. code-block:: python

       from pydantic import AfterValidator, BeforeValidator

       id: Annotated[int, AfterValidator(validate_vlan_id)] = Field(...)
       state_memberships: Annotated[
           list[StateMembershipRef] | None,
           BeforeValidator(none_to_empty_list),
       ] = Field(default_factory=list)

   ``none_to_empty_list`` and ``validate_or_remove`` live in :mod:`flync.core.validators.generic`.

3. ``@field_validator`` — a field-level rule used in **exactly one model**. This is the
   single-use counterpart to an annotated validator: same per-value semantics, but defined next
   to the field that needs it instead of in a shared module. Mark it ``@classmethod`` (the
   convention in ``flync.model``):

   .. code-block:: python

       from pydantic import field_validator, ValidationInfo

       @field_validator("baud_rate")            # default mode is "after"
       @classmethod
       def validate_baud_rate(cls, value: int) -> int:
           if value not in _ALLOWED_CAN_BAUD_RATES:
               raise err_minor(
                   "baud_rate {value} is not a valid CAN baud rate. Allowed values: {allowed}",
                   value=value,
                   allowed=sorted(_ALLOWED_CAN_BAUD_RATES),
                   category=Category.VALUE_RANGE,
                   error_number="049",
               )
           return value

   One validator may name several fields that share the rule (``@field_validator("vlanid",
   "pcp")``). Three shapes cover the field-level cases:

   * **value rule** (default ``mode="after"``) — validate and return the parsed value;
   * ``mode="before"`` — normalize raw input for a single field before parsing (e.g. wrap a
     bare string, coerce ``None`` to ``[]``);
   * **single-field cross-check** — keep ``mode="after"`` and add ``info: ValidationInfo``; read
     other fields from ``info.data`` when the rule involves one field but depends on another:

     .. code-block:: python

         @field_validator("length_of_length_field", mode="after")
         @classmethod
         def validate(cls, value: int, info: ValidationInfo) -> int:
             if info.data["kind"] == "dynamic" and value == 0:
                 raise err_major(
                     "length_of_length_field must be > 0 for dynamic arrays",
                     category=Category.VALUE_RANGE,
                     error_number="140",
                 )
             return value

   **Rule of thumb:** a field-level rule used in exactly one model is a ``@field_validator``.
   The moment the same rule is needed in a *second* model, extract it to
   ``flync.core.validators`` or ``flync.core.datatypes`` and reference it from the
   ``Annotated[...]`` type instead — do not copy the validator body. Cross-field rules that
   touch *multiple distinct fields* stay ``@model_validator(mode="after")``; only a single-field
   check that reads another field via ``info.data`` warrants a field validator.

4. ``@model_validator(mode="before")`` — shape-of-input fixes: defaults for absent blocks and
   legacy-key migration. Takes and returns the raw ``dict``; mark it ``@classmethod`` (the
   convention in ``flync.model``):

   .. code-block:: python

       @model_validator(mode="before")
       @classmethod
       def drop_legacy_role(cls, data: Any) -> Any:
           """Drop a ``role`` left over from an earlier FLYNC version, with a warning."""
           if not isinstance(data, dict) or "role" not in data:
               return data

           warn(
               f"10BASE-T1S MDI config declares 'role' ({data['role']!r}), which FLYNC no longer models and ignores.",
               category=Category.LIFECYCLE,
               error_number="338",
           )
           return {key: value for key, value in data.items() if key != "role"}

5. ``@model_validator(mode="after")`` — cross-field and cross-object rules. Takes/returns
   ``self`` and is annotated ``-> Self``:

   .. code-block:: python

       @model_validator(mode="after")
       def validate_topology_consistency(self) -> Self:
           if self.topology == "multidrop" and self.duplex == "full":
               raise err_major(
                   "10BASE-T1S PHY declares duplex 'full' on topology '{topology}'. "
                   "A shared multidrop segment has to be half duplex.",
                   category=Category.CONSISTENCY,
                   error_number="324",
                   topology=self.topology,
               )
           return self

Uniqueness is enforced **on the owner**, not on the owned item — a child model just declares
``name``; the parent deduplicates its list:

.. code-block:: python

    from flync.core.validators.generic import validate_list_items_unique

    @model_validator(mode="after")
    def validate_unique_ecu_names(self) -> Self:
        validate_list_items_unique([ecu.name for ecu in self.ecus], "ECU names")
        return self

The error catalog
=================

Never raise bare ``ValueError`` / ``assert`` from a model — every finding carries a globally
unique, documented id:

.. code-block:: text

    FLYNC-<MODULE>-<SEVERITY>-<CATEGORY>-<NUMBER>      e.g.  FLYNC-ECU-MAJ-VAL-001

* **MODULE** — auto-resolved from the ``KEY`` variable in the domain package's ``__init__.py``
  (``ECU``, ``SOM``, ``TSN`` ...). Never pass it manually.
* **SEVERITY** — ``WARN`` / ``MIN`` / ``MAJ`` / ``FAT``, from the factory you choose.
* **CATEGORY** — the code for the ``Category`` member you pass. The two spellings differ: you
  write the *member*, the id carries the *code* (:mod:`flync.core.utils.exceptions`).

  .. list-table::
     :header-rows: 1

     * - You pass
       - Id shows
     * - ``Category.VALUE_RANGE``
       - ``VAL``
     * - ``Category.REQUIRED``
       - ``REQ``
     * - ``Category.CONSISTENCY``
       - ``CONS``
     * - ``Category.UNIQUENESS``
       - ``UNIQ``
     * - ``Category.REFERENCE``
       - ``REF``
     * - ``Category.FORMAT``
       - ``FMT``
     * - ``Category.COMPATIBILITY``
       - ``COMP``
     * - ``Category.STRUCTURAL``
       - ``STRUCT``
     * - ``Category.LIFECYCLE``
       - ``LIFE``

* **NUMBER** — three digits, unique across the whole codebase, never reused.

.. code-block:: python

    from flync.core.utils.exceptions import Category, err_major, err_minor, warn

    # the offending object is rejected, loading continues — raise the returned PydanticCustomError
    raise err_major(
        "Port name '{port_name}' is not unique within ECU '{ecu_name}'",
        category=Category.UNIQUENESS,
        error_number="042",
        port_name=port_name,
        ecu_name=ecu_name,
    )

    # field stays usable — warn() is a side effect, do NOT raise it
    warn(
        "Deprecated field '{field}' used",
        category=Category.LIFECYCLE,
        error_number="099",
        field=field,
    )

Message arguments are interpolated into both the message and the catalog entry — name the
offending value, not just the rule.

Choosing a severity
===================

The severity is not a mood — it selects what the loader does with the finding. Pick it from the
consequence you want, not from how bad the mistake feels:

.. list-table::
   :header-rows: 1
   :widths: 12 48 40

   * - Factory
     - What the loader does
     - Choose it when
   * - ``warn``
     - Records the finding and keeps the value. Nothing is raised — call it as a side effect.
     - The config is usable as written: a deprecated key, an ignored leftover from an older
       FLYNC version.
   * - ``err_minor``
     - The component carrying the bad value is not created; validation continues and collects.
       A model may still be returned if nothing worse was found.
     - One field value is wrong and the rest of the object is independent of it.
   * - ``err_major``
     - Collected like a minor, but no model is returned — the caller gets ``None`` plus the full
       error list. The offending location is excised and tracked so loading can continue.
     - The object is unusable, but the rest of the workspace is still worth validating so the
       author sees every problem in one run.
   * - ``err_fatal``
     - Stops validation immediately and re-raises pydantic's ``ValidationError``.
     - Nothing further can be validated meaningfully — reserve it for genuinely unrecoverable
       structure.

Prefer ``err_major`` over ``err_fatal`` by default: aborting on the first problem makes the
author fix the config one error per run. The propagation machinery behind this table is
documented at :ref:`error_propagation`.

Adding or changing an error
===========================

.. code-block:: bash

    flync errors get-next-number    # claim the next free number
    # ... use it in your err_*/warn factory call ...
    flync errors sync               # renumber collisions + regenerate error_catalog.rst

``docs/source/error_catalog.rst`` is generated from the source — never hand-edit it. On a branch
that collided with an id on the base branch, ``flync errors sync --base <ref>`` keeps the base's
number and rewrites yours (including ids pinned in tests).

Testing a rule
==============

Negative tests pin the *exact* error via ``assert_single_error`` or ``assert_single_warning``
(``tests/error_assertions.py``) — a substring ``assert`` passes on any unrelated error:

.. code-block:: python

    from tests.error_assertions import assert_single_error

    with pytest.raises(ValidationError) as exc_info:
        Bitfield(name="corrupt_bitfield", length=8, fields=nine_fields)
    assert_single_error(exc_info, "FLYNC-SOM-MIN-CONS-138", "exceeds the bitfield length (8)")

One fixture triggers exactly one defect; accepted and rejected boundary cases live side by side
in one ``parametrize`` — see *Writing tests* in ``AGENTS.md``.
