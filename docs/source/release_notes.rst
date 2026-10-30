:orphan:

.. _release_notes:

Release Notes
=============

.. seealso::

   For a step-by-step description of how the FLYNC configuration model and public API changed between
   releases (and what you must update to migrate a project), see the :doc:`model_change_history`.

Release 0.16
------------

Quoting of ambiguous strings on save
''''''''''''''''''''''''''''''''''''

Saving a workspace quotes every string that YAML 1.1 readers or ``ruamel.yaml`` would read as a number or a boolean:
binary and underscore-grouped numbers (``0b0101``, ``1_000``), floats without a leading digit (``-.5``) and ``yes``/``no``/``on``/``off``.
Binary ``Bitmask`` literals such as ``"0b0000100000000000"`` therefore keep their width and notation for every reader of
the saved files. The FLYNC loader reads the quoted and the plain forms the same way.
