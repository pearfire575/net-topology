from unittest.mock import patch, MagicMock
import pytest
from net_topology.discovery import (
    DeviceProbe, discover_devices, classify_vendor, classify_device_type,
)
from net_topology.models import Vendor, DeviceType
from net_topology.config import SnmpCredentials


def test_classify_vendor_mikrotik():
    assert classify_vendor("1.3.6.1.4.1.14988.1.1") == Vendor.MIKROTIK

def test_classify_vendor_ubiquiti():
    assert classify_vendor("1.3.6.1.4.1.41112.1.6") == Vendor.UBIQUITI

def test_classify_vendor_zyxel():
    assert classify_vendor("1.3.6.1.4.1.890.1.15") == Vendor.ZYXEL

def test_classify_vendor_unknown():
    assert classify_vendor("1.3.6.1.4.1.9999.1.1") == Vendor.UNKNOWN

def test_classify_device_type_router():
    assert classify_device_type("Router", "1.3.6.1.4.1.14988") == DeviceType.ROUTER

def test_classify_device_type_switch_from_descr():
    assert classify_device_type("EdgeSwitch 24-Port", "") == DeviceType.SWITCH

def test_classify_device_type_ap():
    assert classify_device_type("UniFi AP AC Pro", "") == DeviceType.ACCESS_POINT

def test_classify_device_type_unknown():
    assert classify_device_type("Some device", "") == DeviceType.UNKNOWN

def test_device_probe_dataclass():
    probe = DeviceProbe(
        ip="192.168.1.10", mac="AA:BB:CC:DD:EE:FF", is_managed=True,
        sys_name="sw1", sys_descr="EdgeSwitch", sys_object_id="1.3.6.1.4.1.41112",
        vendor=Vendor.UBIQUITI, device_type=DeviceType.SWITCH,
    )
    assert probe.is_managed is True
    assert probe.vendor == Vendor.UBIQUITI

def test_device_probe_unmanaged():
    probe = DeviceProbe(ip="192.168.1.50", mac="11:22:33:44:55:66", is_managed=False)
    assert probe.is_managed is False
    assert probe.sys_name is None

@patch("net_topology.discovery.SnmpClient")
def test_discover_classifies_responding_device_as_managed(mock_snmp_cls):
    mock_client = MagicMock()
    mock_client.get_sys_info.return_value = {
        "1.3.6.1.2.1.1.5.0": "mikrotik-gw",
        "1.3.6.1.2.1.1.1.0": "RouterOS RB4011",
        "1.3.6.1.2.1.1.2.0": "1.3.6.1.4.1.14988.1",
    }
    mock_snmp_cls.return_value = mock_client
    creds = SnmpCredentials(version="2c", community="public")
    ips_macs = [("192.168.1.1", "AA:BB:CC:DD:EE:FF")]
    results = discover_devices(ips_macs, lambda ip: creds, max_workers=1)
    assert len(results) == 1
    assert results[0].is_managed is True
    assert results[0].vendor == Vendor.MIKROTIK

@patch("net_topology.discovery.SnmpClient")
def test_discover_classifies_unreachable_as_endpoint(mock_snmp_cls):
    from net_topology.snmp import SnmpError
    mock_client = MagicMock()
    mock_client.get_sys_info.side_effect = SnmpError("timeout")
    mock_snmp_cls.return_value = mock_client
    creds = SnmpCredentials(version="2c", community="public")
    ips_macs = [("192.168.1.50", "11:22:33:44:55:66")]
    results = discover_devices(ips_macs, lambda ip: creds, max_workers=1)
    assert len(results) == 1
    assert results[0].is_managed is False
