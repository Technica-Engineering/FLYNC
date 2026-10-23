"""
Binding/resolve helpers for :class:`~flync.model.flync_model.FLYNCModel`.

These back the ``resolve_*`` validator passes that remain on the top-level model: they walk the
system's sockets and bind the in-repository TCP profiles, SOME/IP services / SD timings and
diagnostics (DoIP timings, UDS servers) that deployments reference.
"""

from __future__ import annotations

from collections.abc import Iterator

from flync.model._model_parts._protocol import FLYNCModelProtocol
from flync.model.flync_4_app import App, ServiceConsumerReference
from flync.model.flync_4_diagnostics import (
    DoIPDiscoveryDeployment,
    DoIPServerDeployment,
    DoIPTimingProfile,
    UDSServer,
)
from flync.model.flync_4_ecu import ComputeNode, Controller, TCPOption
from flync.model.flync_4_someip import (
    SDTimings,
    SOMEIPServiceDeployment,
    SOMEIPServiceInterface,
)


class BindingMixin:
    """Walk the system's deployments to resolve profile / service references."""

    def _bind_tcp_profiles(self: FLYNCModelProtocol, tcp_by_id: dict[int, TCPOption]) -> None:
        for sock in self._iter_all_sockets():
            if hasattr(sock, "bind"):
                sock.bind(tcp_by_id)

    def _bind_someip_sockets(
        self: FLYNCModelProtocol,
        services_by_key: dict[tuple[int, int], SOMEIPServiceInterface],
        sd_timings_by_id: dict[str, SDTimings],
    ) -> None:
        for sock in self._iter_all_sockets():
            for dep_union in sock.deployments or []:
                dep = dep_union.root
                if isinstance(dep, SOMEIPServiceDeployment):
                    dep.bind(services_by_key, sd_timings_by_id)

    def _bind_diagnostics_sockets(
        self: FLYNCModelProtocol,
        timings_by_id: dict[str, DoIPTimingProfile],
        servers_by_name: dict[str, UDSServer],
    ) -> None:
        for sock in self._iter_all_sockets():
            for dep_union in sock.deployments or []:
                dep = dep_union.root
                if isinstance(dep, DoIPServerDeployment):
                    dep.bind(servers_by_name, timings_by_id)
                elif isinstance(dep, DoIPDiscoveryDeployment):
                    dep.bind(timings_by_id)

    def _iter_bound_app_consumer_refs(
        self: FLYNCModelProtocol,
    ) -> Iterator[tuple[Controller | ComputeNode, set[tuple[int, int, int]], App, ServiceConsumerReference]]:
        """
        Yield ``(controller, consumed_instances, app, ref)`` for every consumer reference of every app bound to a
        controller, where ``consumed_instances`` is that controller's set of SOME/IP consumer service triples.
        """

        for owner in self.iter_app_binding_owners():
            if not owner.app_bindings:
                continue
            consumed_instances = owner.get_consumed_service_instances()
            for app in owner.app_bindings.apps:
                for ref in app.service_consumer_refs or []:
                    yield owner, consumed_instances, app, ref
