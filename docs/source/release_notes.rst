:orphan:

.. _release_notes:

Release Notes
=============

.. seealso::

   For a step-by-step description of how the FLYNC configuration model and public API changed between
   releases (and what you must update to migrate a project), see the :doc:`model_change_history`.

Release 0.16
------------

Validation uses the workspace's configuration
''''''''''''''''''''''''''''''''''''''''''''''

``validate_workspace`` and ``flync validate`` read the ``.flync/config.yaml`` of a workspace folder when no
configuration is passed, as loading the workspace does. A workspace whose configuration changes how it is read,
such as its file extensions, was reported ``EMPTY`` or broken before.
