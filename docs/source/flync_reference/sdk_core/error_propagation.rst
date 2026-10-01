.. _error_propagation:

Error Propagation
*******************

Custom validators in FLYNC are raising PydanticCustomErrors, to make sure the workspace is loaded as expected.
The different Custom Errors are handled in an error propagation flow that we'll explore on this page.

.. seealso::

   :ref:`validators_and_errors` in the Model Development Guide covers the authoring side -
   which severity to pick, how to claim an error number, and how to pin an error in a test.
   This page documents what the loader then does with the finding.

Overview
--------

There are 3 types of errors defined:

* Minor
* Major
* Fatal

All of them are produced by the factory functions in :mod:`flync.core.utils.exceptions` and
raised directly. Each factory requires a ``category`` and an ``error_number``: together with the
calling package's ``KEY`` they compose the globally unique
``FLYNC-<MODULE>-<SEVERITY>-<CATEGORY>-<NUMBER>`` id that identifies the finding in
:doc:`../../error_catalog`.

Example:

.. code-block:: python

    raise err_minor(
        "{field_type} is wrong type for the field {field_name}",
        category=Category.VALUE_RANGE,
        error_number="001",
        field_type=field_type,
        field_name=field_name,
    )

.. code-block:: python

    raise err_major(
        "{field_type} is wrong type for the field {field_name}",
        category=Category.VALUE_RANGE,
        error_number="002",
        field_type=field_type,
        field_name=field_name,
    )

.. code-block:: python

    raise err_fatal(
        "{field_type} is wrong type for the field {field_name}",
        category=Category.STRUCTURAL,
        error_number="003",
        field_type=field_type,
        field_name=field_name,
    )

A fourth factory, ``warn(...)``, records a non-fatal finding as a side effect and keeps the
value. It takes the same arguments but must **not** be raised.

.. important::

   Pass the interpolated values as ctx keyword arguments rather than building the message with
   an f-string. The arguments are what put the offending value into the rendered catalog entry
   and into the reported error, so an f-string message loses them.

.. note::

   The numbers above are placeholders for illustration. Claim a real one with
   ``flync errors get-next-number`` and run ``flync errors sync`` afterwards - error numbers are
   unique across the whole codebase and are never reused.


Validation policy
-----------------

The :ref:`flync_workspace` provides a loader that uses following validation policy:

.. list-table::
   :class: longtable
   :header-rows: 1
   :align: left

   * - **Error Level**
     - Error Handling
   * - **minor**
     - Minor errors are usually related to an individual field value and are easy to fix.
       in the current version of FLYNC, the component with the minor error will not be created.
       But the validation continues and in case there are only minor issues, the FLYNC model might be created with the list of all collected errors.
   * - **major**
     - Major errors are being collected along with minor ones.
       The validation returns a tuple with **no** FLYNC model (None) and a list of all collected errors.
   * - **fatal**
     - Stops the validation immediately and reraises pydantic's original ValidationError.


This policy is implemented in :func:`flync.core.utils.exceptions_handling.validate_with_policy`.
