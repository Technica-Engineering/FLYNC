

************
FLYNC Model
************

.. hint::

   The main entry point for any FLYNC Model is this class.

.. admonition:: Expand for Schematic
   :collapsible: closed

   .. mermaid:: ../../_static/mermaid/model.mmd

.. autoclass:: flync.model.flync_model.FLYNCModel()
   :members:


Multicasting
#############

.. seealso::

   Multicast Group Memberships are dynamically collected per-ECU.
   Go to :ref:`ECU Multicast Group Memberships <ecu_multicast>` to understand how they are populated.

On system-level these Multicast Groups are then validated:

1. For a multicast group, at least one TX node is expected.

2. A tx node must reach all rx nodes of the group.

.. hint::

   After successful validation of the Multicast Groups,
   the switch config is automatically updated with the relevant group entries in the respective :class:`~flync.model.flync_4_ecu.switch.VLANEntry`.
