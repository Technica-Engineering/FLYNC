.. _security:

****************
flync_4_security
****************

.. _macsec:

MACsec Configuration
####################

.. admonition:: Expand for Schematic
   :collapsible: closed

   .. mermaid:: ../../_static/mermaid/macsec.mmd

.. hint::
   Find a YAML example for MACsec inside the :ref:`Controller example <controller>` (key macsec_config).

.. autoclass:: flync.model.flync_4_security.MACsecConfig()
.. autoclass:: flync.model.flync_4_security.CipherSuiteBaseModel()
.. autoclass:: flync.model.flync_4_security.IntegrityWithoutConfidentiality()
.. autoclass:: flync.model.flync_4_security.IntegrityWithConfidentiality()

.. _firewall:

Firewall Configuration
######################

.. admonition:: Expand for Schematic
   :collapsible: closed

   .. mermaid:: ../../_static/mermaid/firewall.mmd

.. autoclass:: flync.model.flync_4_security.Firewall()
.. autoclass:: flync.model.flync_4_security.FirewallRule()
