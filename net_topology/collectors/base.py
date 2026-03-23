from __future__ import annotations

from abc import ABC, abstractmethod

from net_topology.config import SnmpCredentials
from net_topology.discovery import DeviceProbe
from net_topology.models import Device


class BaseCollector(ABC):
    def __init__(self, probe: DeviceProbe, credentials: SnmpCredentials):
        self.probe = probe
        self.credentials = credentials

    @abstractmethod
    async def collect(self) -> tuple[Device, list[dict], list[dict]]:
        """Collect device data.

        Returns:
            (device, lldp_neighbors, fdb_entries)
            - device: populated Device object
            - lldp_neighbors: list of dicts with keys: local_port, remote_port, remote_chassis, remote_name
            - fdb_entries: list of dicts with keys: mac, port
        """
        ...
