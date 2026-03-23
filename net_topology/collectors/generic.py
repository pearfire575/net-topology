from __future__ import annotations

import logging
import re

from net_topology.collectors.base import BaseCollector
from net_topology.config import SnmpCredentials
from net_topology.discovery import DeviceProbe
from net_topology.models import Device, Interface
from net_topology.snmp import (
    SnmpClient,
    OID_IF_TABLE,
    OID_IF_X_TABLE,
    OID_LLDP_REM_TABLE,
    OID_CDP_CACHE_TABLE,
    OID_DOT1Q_VLAN_STATIC,
    OID_DOT1D_TP_FDB,
    OID_DOT1Q_TP_FDB,
)

logger = logging.getLogger(__name__)

# Sub-OIDs under ifTable (1.3.6.1.2.1.2.2.1)
IF_DESCR = "1.3.6.1.2.1.2.2.1.2"
IF_PHYS_ADDR = "1.3.6.1.2.1.2.2.1.6"
IF_OPER_STATUS = "1.3.6.1.2.1.2.2.1.8"
IF_HIGH_SPEED = "1.3.6.1.2.1.31.1.1.1.15"

OPER_STATUS_MAP = {"1": "up", "2": "down", "3": "testing"}


def _extract_index(oid: str, prefix: str) -> str | None:
    """Extract the trailing index from an OID after a prefix."""
    if oid.startswith(prefix + "."):
        return oid[len(prefix) + 1 :]
    return None


def _normalize_mac(raw: str) -> str:
    """Convert hex string like 0xaabbccddeeff to AA:BB:CC:DD:EE:FF."""
    raw = raw.strip()
    if raw.startswith("0x"):
        raw = raw[2:]
    raw = re.sub(r"[^0-9a-fA-F]", "", raw)
    if len(raw) == 12:
        return ":".join(raw[i : i + 2] for i in range(0, 12, 2)).upper()
    return raw


class GenericSnmpCollector(BaseCollector):
    def __init__(self, probe: DeviceProbe, credentials: SnmpCredentials):
        super().__init__(probe, credentials)
        self.client = SnmpClient(probe.ip, credentials)

    async def collect(self) -> tuple[Device, list[dict], list[dict]]:
        interfaces = await self._collect_interfaces()
        lldp_entries = await self._collect_lldp()
        cdp_entries = await self._collect_cdp()
        fdb_entries = await self._collect_fdb()

        if not lldp_entries and not cdp_entries:
            logger.warning(
                "Device %s (%s) returned no LLDP or CDP neighbors. "
                "Check if LLDP/CDP is enabled.",
                self.probe.sys_name,
                self.probe.ip,
            )

        all_macs = [self.probe.mac] if self.probe.mac else []
        for iface in interfaces:
            if iface.mac and iface.mac not in all_macs:
                all_macs.append(iface.mac)

        device = Device(
            hostname=self.probe.sys_name or self.probe.ip,
            ip_addresses=[self.probe.ip],
            mac_addresses=all_macs,
            device_type=self.probe.device_type,
            vendor=self.probe.vendor,
            model=None,
            firmware=self.probe.sys_descr,
            interfaces=interfaces,
        )

        # Merge LLDP + CDP neighbor entries
        all_neighbors = lldp_entries + [
            {**e, "protocol": "cdp"} for e in cdp_entries
        ]
        for entry in lldp_entries:
            entry.setdefault("protocol", "lldp")

        return device, all_neighbors, fdb_entries

    async def _collect_interfaces(self) -> list[Interface]:
        descr_walk = await self.client.walk(IF_DESCR)
        phys_walk = await self.client.walk(IF_PHYS_ADDR)
        status_walk = await self.client.walk(IF_OPER_STATUS)
        speed_walk = await self.client.walk(IF_HIGH_SPEED)

        descrs = {}
        for oid, val in descr_walk:
            idx = _extract_index(oid, IF_DESCR)
            if idx:
                descrs[idx] = val

        phys_addrs = {}
        for oid, val in phys_walk:
            idx = _extract_index(oid, IF_PHYS_ADDR)
            if idx:
                phys_addrs[idx] = _normalize_mac(val)

        statuses = {}
        for oid, val in status_walk:
            idx = _extract_index(oid, IF_OPER_STATUS)
            if idx:
                statuses[idx] = OPER_STATUS_MAP.get(val, "unknown")

        speeds = {}
        for oid, val in speed_walk:
            idx = _extract_index(oid, IF_HIGH_SPEED)
            if idx:
                try:
                    mbps = int(val)
                    speeds[idx] = f"{mbps}Mbps" if mbps < 1000 else f"{mbps // 1000}Gbps"
                except ValueError:
                    speeds[idx] = None

        interfaces = []
        for idx, name in descrs.items():
            iface = Interface(
                name=name,
                index=int(idx) if idx.isdigit() else 0,
                mac=phys_addrs.get(idx),
                speed=speeds.get(idx),
                status=statuses.get(idx, "unknown"),
                vlans=[],
            )
            interfaces.append(iface)

        return interfaces

    async def _collect_lldp(self) -> list[dict]:
        raw = await self.client.walk(OID_LLDP_REM_TABLE)
        if not raw:
            return []

        entries_by_key: dict[str, dict] = {}

        for oid, val in raw:
            parts = oid.split(".")
            try:
                prefix_len = len(OID_LLDP_REM_TABLE.split("."))
                sub_oid = parts[prefix_len]
                key = ".".join(parts[prefix_len + 1 :])
            except (IndexError, ValueError):
                continue

            if key not in entries_by_key:
                entries_by_key[key] = {}

            # Sub-OID meanings in lldpRemTable:
            # 5 = lldpRemChassisId
            # 7 = lldpRemPortId
            # 9 = lldpRemSysName
            if sub_oid == "5":
                entries_by_key[key]["remote_chassis"] = _normalize_mac(val)
            elif sub_oid == "7":
                entries_by_key[key]["remote_port"] = val
            elif sub_oid == "9":
                entries_by_key[key]["remote_name"] = val

        result = []
        for key, entry in entries_by_key.items():
            key_parts = key.split(".")
            if len(key_parts) >= 2:
                local_port_idx = key_parts[1]
                entry["local_port_index"] = local_port_idx
            entry["protocol"] = "lldp"
            result.append(entry)

        return result

    async def _collect_cdp(self) -> list[dict]:
        raw = await self.client.walk(OID_CDP_CACHE_TABLE)
        if not raw:
            return []

        entries_by_key: dict[str, dict] = {}

        for oid, val in raw:
            parts = oid.split(".")
            prefix_len = len(OID_CDP_CACHE_TABLE.split("."))
            try:
                sub_oid = parts[prefix_len]
                key = ".".join(parts[prefix_len + 1 :])
            except (IndexError, ValueError):
                continue

            if key not in entries_by_key:
                entries_by_key[key] = {}

            if sub_oid == "6":
                entries_by_key[key]["remote_name"] = val
            elif sub_oid == "7":
                entries_by_key[key]["remote_port"] = val

        return list(entries_by_key.values())

    async def _collect_fdb(self) -> list[dict]:
        """Collect MAC address (FDB) table to map endpoints to ports."""
        raw = await self.client.walk(OID_DOT1Q_TP_FDB)
        is_qbridge = bool(raw)
        if not raw:
            raw = await self.client.walk(OID_DOT1D_TP_FDB)

        entries = []
        for oid, val in raw:
            parts = oid.split(".")
            try:
                mac_octets = parts[-6:]
                mac = ":".join(f"{int(o):02X}" for o in mac_octets)
                port_index = val
                entries.append({"mac": mac, "port_index": port_index})
            except (ValueError, IndexError):
                continue

        return entries
