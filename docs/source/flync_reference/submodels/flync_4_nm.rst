.. _flync_4_nm:

**********
flync_4_nm
**********

Network Management — State Management Groups
############################################

.. note::
   The central group registry is placed in the directory 📁
   ``communication/state_management/`` (file ``groups.flync.yaml``).
   This is a **non-mandatory** directory for the FLYNC configuration.
   Memberships are declared entity-side — on ECUs, controllers, and buses.

FLYNC models network management vendor-neutrally: a **state management
group** owns only its identity, a reference to an ordinary NM PDU
(``pdu_usage: network_management``), and a reference to a shared, reusable
timing profile.
It has **no member list** — the effective member set is **derived** during
validation from the memberships declared on the entities.

.. autoclass:: flync.model.flync_4_nm.StateManagementConfig()
.. autoclass:: flync.model.flync_4_nm.StateManagementGroup()
.. autoclass:: flync.model.flync_4_nm.GroupTiming()
.. autoclass:: flync.model.flync_4_nm.AnnouncementPhaseTiming()
.. autoclass:: flync.model.flync_4_nm.SleepTiming()

.. admonition:: Expand for a YAML example - 📄 ``timing_profiles.flync.yaml`` + ``groups.flync.yaml``
   :collapsible: closed

   .. code-block:: yaml

      # timing_profiles.flync.yaml — reusable, referenced by name from any group
      timing_profiles:
      - name: standard
        cycle_time_ms: 500              # message sending cycle in normal operation
        announcement:                   # optional: announcement phase
          duration_ms: 1000             # total duration of the announcement phase
          burst_count: 5                # number of initial burst PDUs
          burst_cycle_time_ms: 20       # cycle time for the initial burst PDUs
        sleep:                          # go-to-sleep progression
          timeout_ms: 2000              # timeout before preparing to go to sleep
          wait_before_sleep_ms: 1500    # time of preparing to go to sleep

      # groups.flync.yaml
      groups:
      - name: VEHICLE
        description: Vehicle-wide group using PDU_NmMessage.
        nm_pdu: PDU_NmMessage
        timing_profile: standard
        extensions:            # optional OEM/tool-specific key/value hooks
          parameter_a: value_a
          parameter_b: value_b


Memberships
###########

Entities declare membership themselves; the group never lists members.

.. autoclass:: flync.model.flync_4_nm.StateMembershipRef()

Declaration sites:

- **Controller** (recommended for multi-controller ECUs) — 📄
  ``state_memberships.flync.yaml`` inside the controller folder.
- **ECU** (whole-ECU granularity, also used by abstract ECUs) — 📄
  ``state_memberships.flync.yaml`` inside the ECU folder.
- **Bus** (bus-level membership) — inline ``state_memberships`` in the bus
  file: the whole bus is ONE participant, kept awake while requested and
  asleep as a unit when released, never expanded into per-attached-ECU
  participants. It may reference several relevance bits when the bus is needed
  for several functions (default: a single bit named after the bus), but wakes
  as a whole for any of them. This is the **only** option for **LIN** — LIN
  carries no NM message, so the bus can only move as a unit, driven by its
  master, which is either the source of the group state (e.g. a central
  gateway) or receives it on another bus.

Which variant applies depends on the transport:

- **LIN** — bus-level only. LIN carries no NM message, so a LIN bus can only
  participate as a whole (via its master). The master itself may additionally
  hold its own membership in the same group (e.g. a central gateway that also
  participates with its own functions).
- **CAN** — **either** variant, decided **per CAN bus**: node-level (its ECUs
  / controllers participate individually, per function) **or** bus-level (the
  whole CAN bus is one participant). Both are valid choices — neither is a
  default. Per CAN Bus choose **one** variant — node-level or bus-level — never both; mixing
  them for the same bus is rejected during validation.

- **Ethernet** — node-level (its controllers / ECUs); Ethernet segments carry
  no bus-level object.

The two roles:

- **participant** — references one or more relevance bits (the vehicle
  functions it takes part in, listed together in a single membership) and
  joins the wake/sleep decision.
- **observer** — receives the group's NM PDU and reacts to the group **as a
  whole** (e.g. a switch core pulling a wake line while the group is active);
  it watches the entire group, not individual bits, so it references no bit and
  never influences the decision.

.. admonition:: Expand for a YAML example - 📄 ``state_memberships.flync.yaml``
   :collapsible: closed

   .. code-block:: yaml

      state_memberships:
      - group: VEHICLE
        role: participant          # or: observer
        relevance_bits:            # vehicle functions this member references; list
          - AutonomousDriving      # several in ONE membership instead of
          - OnlineCommunication    # repeating the block; defaults to the
                                   # entity name. Several members may share a
                                   # bit. Absent for observers.

Each relevance bit has two states, *requested* and *released*; an entity that
holds several bits or memberships sleeps only when **all** of them are
released. The role is also the permission model: only participants may request
the group state — setting a relevance bit — which is why declaring
``relevance_bits`` on an observer membership is rejected.


Transport independence and validation
#####################################

The group's NM PDU is bound to a transport with the ordinary PDU mechanisms:

- **Ethernet** — a ``pdu_sender`` / ``pdu_receiver`` socket deployment,
  optionally through a Container PDU.
- **CAN / LIN** — ``sender_frames`` / ``receiver_frames`` on the interface.

Validation cross-checks role against binding:

.. list-table::
   :header-rows: 1
   :widths: 75 25

   * - Check
     - Status
   * - every referenced group exists in the registry
     - error
   * - every group has at least one participant
     - error
   * - the group's references resolve — ``nm_pdu`` to a PDU flagged
       ``pdu_usage: network_management``, ``timing_profile`` to a defined
       profile
     - error
   * - role vs. transport binding: participants need a TX and an RX path,
       observers an RX path; a CAN bus member needs a frame binding plus an
       attached sender; a LIN bus member needs a master that knows the group
       state (as its source, or by receiving it on another bus)
     - error
   * - a CAN bus uses a single membership variant (whole-bus or per-node),
       not both
     - error
   * - redundant declarations
     - warning
   * - every claimed relevance bit exists in the PDU's vector
     - error
   * - the group's cycle time is plausible on every CAN bus carrying the NM
       PDU — physically
       feasible at the bus baud rate and consistent with the frame's
       configured cyclic timing (LIN and Ethernet out of scope)
     - warning


Cross-bus forwarding
####################

A group needs no coordinator object. When a group spans several buses, an
ordinary gateway forwards its NM PDU from one bus onto the next using plain
``sender_frames`` / ``receiver_frames`` — the same mechanism any PDU uses to
cross a bus. Each node reads the relevance vector it receives and applies the
sleep decision locally, so the group's behaviour emerges from ordinary
forwarding plus each entity's local sleep decision, not from a dedicated
coordinating role.

In ``examples/flync_example`` the ``zonal_gateway`` does exactly this: it
receives the ``VEHICLE`` NM PDU on Ethernet and forwards it onto ``BodyCAN``
through an ordinary ``Frame_Nm_Gateway`` sender frame.


Showcase
########

``examples/flync_example`` exercises every use case: one vehicle-wide group
(``VEHICLE``) across Ethernet, BodyCAN, DiagCAN, and BodyLIN, with relevance
bits that are vehicle **functions** (``AutonomousDriving`` /
``OnlineCommunication`` / ``Comfort``), all three declaration sites, both
roles, a gateway forwarding the NM PDU onto a CAN bus, an ECU referencing several
function bits, and a LIN bus that participates without an NM frame. The walkthrough with the full
use-case map lives in the :ref:`NM section of the example documentation <flync_example_nm>`.
