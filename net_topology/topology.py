from __future__ import annotations

import logging
import socket
from net_topology.models import Device, Link, Endpoint

logger = logging.getLogger(__name__)


def build_links(
    device_lldp: dict[str, tuple[Device, list[dict]]],
) -> list[Link]:
    """Correlate LLDP/CDP neighbor entries into deduplicated links."""
    mac_to_device: dict[str, Device] = {}
    for device_id, (device, _) in device_lldp.items():
        for mac in device.mac_addresses:
            mac_to_device[mac.upper()] = device

    # Track seen device pairs to deduplicate bidirectional LLDP reports
    seen_pairs: set[tuple[str, str]] = set()
    links: list[Link] = []

    for device_id, (device, neighbors) in device_lldp.items():
        port_idx_to_name = {}
        for iface in device.interfaces:
            port_idx_to_name[str(iface.index)] = iface.name

        for neighbor in neighbors:
            remote_chassis = neighbor.get("remote_chassis", "").upper()
            remote_port = neighbor.get("remote_port", "unknown")
            remote_name = neighbor.get("remote_name", "unknown")
            local_port_idx = neighbor.get("local_port_index", "")
            protocol = neighbor.get("protocol", "lldp")

            local_port = port_idx_to_name.get(local_port_idx, f"port-{local_port_idx}")

            remote_device = mac_to_device.get(remote_chassis)
            remote_id = remote_device.id if remote_device else f"d-{remote_chassis.lower().replace(':', '')}"
            remote_dev_name = remote_device.hostname if remote_device else remote_name

            # Deduplicate by sorted device pair
            pair = (min(device.id, remote_id), max(device.id, remote_id))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            if device.id < remote_id:
                link = Link(
                    device_a_id=device.id,
                    device_a_name=device.hostname,
                    port_a=local_port,
                    device_b_id=remote_id,
                    device_b_name=remote_dev_name,
                    port_b=remote_port,
                    discovered_via=protocol,
                )
            else:
                link = Link(
                    device_a_id=remote_id,
                    device_a_name=remote_dev_name,
                    port_a=remote_port,
                    device_b_id=device.id,
                    device_b_name=device.hostname,
                    port_b=local_port,
                    discovered_via=protocol,
                )

            links.append(link)

    return links


def _reverse_dns(ip: str) -> str | None:
    """Try reverse DNS lookup. Returns hostname or None."""
    try:
        hostname, _, _ = socket.gethostbyaddr(ip)
        return hostname
    except (socket.herror, socket.gaierror, OSError):
        return None


def map_endpoints(
    fdb_data: dict[str, tuple[Device, list[dict]]],
    trunk_ports: set[tuple[str, str]],
    arp_entries: list[tuple[str, str]],
) -> list[Endpoint]:
    """Map endpoint MACs to switch ports using FDB tables."""
    mac_to_ip: dict[str, str] = {}
    for ip, mac in arp_entries:
        mac_to_ip[mac.upper()] = ip

    mac_sightings: dict[str, list[tuple[Device, str, bool]]] = {}

    for device_id, (device, fdb_entries) in fdb_data.items():
        port_idx_to_name = {}
        for iface in device.interfaces:
            port_idx_to_name[str(iface.index)] = iface.name

        for entry in fdb_entries:
            mac = entry.get("mac", "").upper()
            port_idx = str(entry.get("port_index", ""))
            port_name = port_idx_to_name.get(port_idx, f"port-{port_idx}")
            is_trunk = (device_id, port_idx) in trunk_ports

            if mac not in mac_sightings:
                mac_sightings[mac] = []
            mac_sightings[mac].append((device, port_name, is_trunk))

    endpoints = []
    for mac, sightings in mac_sightings.items():
        access_sightings = [s for s in sightings if not s[2]]
        best = access_sightings[0] if access_sightings else sightings[0]
        device, port_name, _ = best

        ip = mac_to_ip.get(mac, "")
        if not ip:
            continue

        hostname = _reverse_dns(ip)

        endpoints.append(
            Endpoint(
                ip=ip,
                mac=mac,
                hostname=hostname,
                seen_on_device=device.hostname,
                seen_on_port=port_name,
            )
        )

    return endpoints
