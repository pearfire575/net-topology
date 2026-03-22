from unittest.mock import patch
import pytest
from net_topology.topology import build_links, map_endpoints
from net_topology.models import Device, Interface, Link, Endpoint, Vendor, DeviceType


def make_device(hostname, ip, mac, interfaces=None):
    return Device(
        hostname=hostname,
        ip_addresses=[ip],
        mac_addresses=[mac],
        device_type=DeviceType.SWITCH,
        vendor=Vendor.UNKNOWN,
        interfaces=interfaces or [],
    )


def test_build_links_from_matching_lldp():
    """When both devices report each other via LLDP, produce one deduplicated link."""
    dev_a = make_device("sw1", "192.168.1.1", "AA:BB:CC:DD:EE:01")
    dev_b = make_device("sw2", "192.168.1.2", "AA:BB:CC:DD:EE:02")

    lldp_a = [
        {
            "remote_chassis": "AA:BB:CC:DD:EE:02",
            "remote_port": "gi1",
            "remote_name": "sw2",
            "local_port_index": "1",
            "protocol": "lldp",
        }
    ]
    lldp_b = [
        {
            "remote_chassis": "AA:BB:CC:DD:EE:01",
            "remote_port": "ether1",
            "remote_name": "sw1",
            "local_port_index": "1",
            "protocol": "lldp",
        }
    ]

    device_lldp = {dev_a.id: (dev_a, lldp_a), dev_b.id: (dev_b, lldp_b)}
    links = build_links(device_lldp)

    assert len(links) == 1
    link = links[0]
    assert link.discovered_via == "lldp"
    names = {link.device_a_name, link.device_b_name}
    assert names == {"sw1", "sw2"}


def test_build_links_one_sided_lldp():
    """When only one device reports a neighbor, still create the link."""
    dev_a = make_device("sw1", "192.168.1.1", "AA:BB:CC:DD:EE:01")

    lldp_a = [
        {
            "remote_chassis": "AA:BB:CC:DD:EE:02",
            "remote_port": "gi1",
            "remote_name": "sw2",
            "local_port_index": "1",
            "protocol": "lldp",
        }
    ]

    device_lldp = {dev_a.id: (dev_a, lldp_a)}
    links = build_links(device_lldp)

    assert len(links) == 1


def test_build_links_no_duplicates():
    """Same link reported by both sides should not produce two entries."""
    dev_a = make_device("sw1", "192.168.1.1", "AA:BB:CC:DD:EE:01")
    dev_b = make_device("sw2", "192.168.1.2", "AA:BB:CC:DD:EE:02")

    lldp_a = [
        {
            "remote_chassis": "AA:BB:CC:DD:EE:02",
            "remote_port": "gi1",
            "remote_name": "sw2",
            "local_port_index": "1",
            "protocol": "lldp",
        }
    ]
    lldp_b = [
        {
            "remote_chassis": "AA:BB:CC:DD:EE:01",
            "remote_port": "ether1",
            "remote_name": "sw1",
            "local_port_index": "1",
            "protocol": "lldp",
        }
    ]

    device_lldp = {dev_a.id: (dev_a, lldp_a), dev_b.id: (dev_b, lldp_b)}
    links = build_links(device_lldp)

    assert len(links) == 1


def test_map_endpoints_prefers_access_port():
    """When a MAC appears on multiple switches, prefer the one with an access port."""
    dev_a = make_device(
        "core-sw", "192.168.1.1", "AA:BB:CC:DD:EE:01",
        interfaces=[Interface(name="trunk1", index=1, status="up")]
    )
    dev_b = make_device(
        "edge-sw", "192.168.1.2", "AA:BB:CC:DD:EE:02",
        interfaces=[Interface(name="gi12", index=12, status="up")]
    )

    fdb_data = {
        dev_a.id: (dev_a, [{"mac": "11:22:33:44:55:66", "port_index": "1"}]),
        dev_b.id: (dev_b, [{"mac": "11:22:33:44:55:66", "port_index": "12"}]),
    }

    trunk_ports = {(dev_a.id, "1")}

    endpoints = map_endpoints(
        fdb_data,
        trunk_ports,
        arp_entries=[("192.168.1.50", "11:22:33:44:55:66")],
    )

    assert len(endpoints) == 1
    assert endpoints[0].seen_on_device == "edge-sw"
    assert endpoints[0].seen_on_port == "gi12"


@patch("net_topology.topology.socket.gethostbyaddr")
def test_map_endpoints_resolves_hostname(mock_dns):
    """Endpoint hostname should come from reverse DNS or be None."""
    mock_dns.return_value = ("giacomo-pc.local", [], ["192.168.1.50"])

    dev = make_device(
        "sw1", "192.168.1.1", "AA:BB:CC:DD:EE:01",
        interfaces=[Interface(name="gi5", index=5, status="up")]
    )

    fdb_data = {
        dev.id: (dev, [{"mac": "11:22:33:44:55:66", "port_index": "5"}]),
    }

    endpoints = map_endpoints(
        fdb_data,
        trunk_ports=set(),
        arp_entries=[("192.168.1.50", "11:22:33:44:55:66")],
    )

    assert len(endpoints) == 1
    assert endpoints[0].hostname == "giacomo-pc.local"
