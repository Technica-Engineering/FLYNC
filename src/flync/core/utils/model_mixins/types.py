"""
Shared type aliases of the :class:`~flync.model.flync_model.FLYNCModel` mixins.
"""

from __future__ import annotations

from flync.model.flync_4_diagnostics import DoIPDiscoveryDeployment, DoIPServerDeployment
from flync.model.flync_4_signal.forwarder import PDUForwarder
from flync.model.flync_4_signal.pdu_deployment import PDUReceiver, PDUSender
from flync.model.flync_4_someip import SOMEIPSDDeployment, SOMEIPServiceConsumer, SOMEIPServiceProvider

SocketDeployment = (
    SOMEIPServiceConsumer
    | SOMEIPServiceProvider
    | SOMEIPSDDeployment
    | PDUSender
    | PDUReceiver
    | PDUForwarder
    | DoIPServerDeployment
    | DoIPDiscoveryDeployment
)
"""The root type of :class:`~flync.model.flync_4_ecu.sockets.DeploymentUnion` — any deployment a socket can carry."""
