:orphan:

.. _release_notes:

Release Notes
=============

.. seealso::

   For a step-by-step description of how the FLYNC configuration model and public API changed between
   releases (and what you must update to migrate a project), see the :doc:`model_change_history`.

Release 0.16
------------

Improve FLYNC_4_App
'''''''''''''''''''

Adding support for CAN and J1939 references. Also adding IPC.

Package versioning
''''''''''''''''''

The version tag pattern now understands pre-release stages (``release-0.15.0-rc1`` builds as ``0.15.0rc1``), commits after
a tag build as the next ``.devN`` version, and ``main`` is anchored by a ``release-<next minor>.0-dev0`` tag set when a
release branch is cut (see ``CONTRIBUTING.md``).
