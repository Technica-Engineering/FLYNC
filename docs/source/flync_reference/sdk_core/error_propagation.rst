.. _error_propagation:

Error Propagation
*******************

Custom validators in FLYNC are raising PydanticCustomErrors, to make sure the workspace is loaded as expected.
The different Custom Errors are handled in an error propagation flow that we'll explore on this page.

Overview
--------

There are 3 types of errors defined:

* Minor
* Major
* Fatal

All of them can be retrieved from the factory functions from :mod:`flync.core.utils.exceptions`
and raised directly.

Example:

.. code-block:: python

    raise err_minor(
        "{field_type} is wrong type for the field {field_name}",
        field_type=field_type,
        field_name=field_name
    )

.. code-block:: python

    raise err_major(
        "{field_type} is wrong type for the field {field_name}",
        field_type=field_type,
        field_name=field_name
    )

.. code-block:: python

    raise err_fatal(
        "{field_type} is wrong type for the field {field_name}",
        field_type=field_type,
        field_name=field_name
    )


.. tip:: It is not mandatory to use ctx keyword arguments, you can simply use an f-string for error message.


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
