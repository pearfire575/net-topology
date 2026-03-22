from net_topology.models import (
    Interface,
    Device,
    Link,
    Endpoint,
    ScanResult,
    DeviceType,
    Vendor,
)
import json
from datetime import datetime, timezone


def test_device_id_from_mac():
    """Device id is derived from lowest MAC address."""
    dev = Device(
        hostname="sw1",
        ip_addresses=["192.168.1.1"],
        mac_addresses=["BB:CC:DD:EE:FF:00", "AA:BB:CC:DD:EE:FF"],
        device_type=DeviceType.SWITCH,
        vendor=Vendor.UNKNOWN,
    )
    assert dev.id == "d-aabbccddeeff"


def test_device_id_single_mac():
    dev = Device(
        hostname="sw1",
        ip_addresses=["10.0.0.1"],
        mac_addresses=["AA:BB:CC:DD:EE:FF"],
        device_type=DeviceType.ROUTER,
        vendor=Vendor.MIKROTIK,
    )
    assert dev.id == "d-aabbccddeeff"


def test_interface_dataclass():
    iface = Interface(
        name="ether1",
        index=1,
        mac="AA:BB:CC:DD:EE:F0",
        speed="1Gbps",
        status="up",
        vlans=[1, 10],
    )
    assert iface.name == "ether1"
    assert iface.vlans == [1, 10]


def test_link_dataclass():
    link = Link(
        device_a_id="d-aabbccddeeff",
        device_a_name="sw1",
        port_a="ether1",
        device_b_id="d-112233445566",
        device_b_name="sw2",
        port_b="gi1",
        discovered_via="lldp",
    )
    assert link.device_a_id == "d-aabbccddeeff"
    assert link.discovered_via == "lldp"


def test_endpoint_dataclass():
    ep = Endpoint(
        ip="192.168.1.50",
        mac="11:22:33:44:55:66",
        hostname="pc1",
        seen_on_device="sw1",
        seen_on_port="gi12",
    )
    assert ep.ip == "192.168.1.50"
    assert ep.hostname == "pc1"


def test_endpoint_hostname_nullable():
    ep = Endpoint(
        ip="192.168.1.51",
        mac="11:22:33:44:55:77",
        hostname=None,
        seen_on_device="sw1",
        seen_on_port="gi13",
    )
    assert ep.hostname is None


def test_scan_result_to_dict():
    ts = datetime(2026, 3, 22, 15, 30, 0, tzinfo=timezone.utc)
    dev = Device(
        hostname="rtr",
        ip_addresses=["192.168.1.1"],
        mac_addresses=["AA:BB:CC:DD:EE:FF"],
        device_type=DeviceType.ROUTER,
        vendor=Vendor.MIKROTIK,
        model="RB4011",
        firmware="RouterOS 7.14",
        interfaces=[],
    )
    result = ScanResult(
        scan_timestamp=ts,
        seed_device="192.168.1.1",
        devices=[dev],
        links=[],
        endpoints=[],
    )
    d = result.to_dict()
    assert d["schema_version"] == "1.0"
    assert d["scan_timestamp"] == "2026-03-22T15:30:00+00:00"
    assert d["devices"][0]["id"] == "d-aabbccddeeff"
    assert d["devices"][0]["type"] == "router"
    assert d["devices"][0]["vendor"] == "mikrotik"
    # Must be JSON-serializable
    json.dumps(d)


def test_device_type_enum():
    assert DeviceType.ROUTER.value == "router"
    assert DeviceType.SWITCH.value == "switch"
    assert DeviceType.ACCESS_POINT.value == "access_point"
    assert DeviceType.FIREWALL.value == "firewall"
    assert DeviceType.UNKNOWN.value == "unknown"


def test_vendor_enum():
    assert Vendor.MIKROTIK.value == "mikrotik"
    assert Vendor.UBIQUITI.value == "ubiquiti"
    assert Vendor.ZYXEL.value == "zyxel"
    assert Vendor.UNKNOWN.value == "unknown"
