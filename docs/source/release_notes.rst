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

YAML parsing on PyYAML
''''''''''''''''''''''

``ruamel.yaml`` is replaced by PyYAML (libyaml when available), which loads, composes and dumps documents roughly 7-18x faster.
All access goes through ``flync.core.utils.yaml_io``, which keeps the YAML 1.2 core schema (``yes``/``no`` stay strings, ``0875`` is a
number, MAC-like values stay strings) and still rejects duplicate mapping keys.

SOME/IP eventgroup serialization
''''''''''''''''''''''''''''''''

Saving a workspace now writes the members of a SOME/IP eventgroup as references to the service's events and fields, instead of
a full copy of each event and field. Reloading a saved service no longer fails with ``FLYNC-SOM-MIN-REF-136`` after an event
or field is edited in the service's ``events`` or ``fields`` list.

An eventgroup member can be referenced by name or by identifier (event ``id``, field ``notifier_id``). A name shared by several
events/fields of the service is rejected with ``FLYNC-SOM-MIN-REF-421``; such members are referenced by identifier, and saving
writes them that way.

Package versioning
''''''''''''''''''

The version tag pattern now understands pre-release stages (``release-0.15.0-rc1`` builds as ``0.15.0rc1``), commits after
a tag build as the next ``.devN`` version, and ``main`` is anchored by a ``release-<next minor>.0-dev0`` tag set when a
release branch is cut (see ``CONTRIBUTING.md``).
