from unittest.mock import MagicMock, patch
import pytest
from net_topology.collectors.base import BaseCollector
from net_topology.collectors.generic import GenericSnmpCollector
from net_topology.discovery import DeviceProbe
from net_topology.models import Vendor, DeviceType, Device
from net_topology.config import SnmpCredentials


@pytest.fixture
def probe():
    return DeviceProbe(
        ip="192.168.1.2",
        mac="AA:BB:CC:DD:EE:FF",
        is_managed=True,
        sys_name="zyxel-sw",
        sys_descr="Zyxel GS1920-24",
        sys_object_id="1.3.6.1.4.1.890.1.15",
        vendor=Vendor.ZYXEL,
        device_type=DeviceType.SWITCH,
    )


@pytest.fixture
def creds():
    return SnmpCredentials(version="2c", community="public")


def test_generic_collector_is_base_collector():
    assert issubclass(GenericSnmpCollector, BaseCollector)


@patch("net_topology.collectors.generic.SnmpClient")
def test_collect_returns_device(mock_snmp_cls, probe, creds):
    mock_client = MagicMock()

    # Mock interface walk
    mock_client.walk.side_effect = lambda oid: {
        # ifDescr
        "1.3.6.1.2.1.2.2.1.2": [
            ("1.3.6.1.2.1.2.2.1.2.1", "gi1"),
            ("1.3.6.1.2.1.2.2.1.2.2", "gi2"),
        ],
        # ifPhysAddress
        "1.3.6.1.2.1.2.2.1.6": [
            ("1.3.6.1.2.1.2.2.1.6.1", "0xaabbccddeef0"),
            ("1.3.6.1.2.1.2.2.1.6.2", "0xaabbccddeef1"),
        ],
        # ifOperStatus
        "1.3.6.1.2.1.2.2.1.8": [
            ("1.3.6.1.2.1.2.2.1.8.1", "1"),
            ("1.3.6.1.2.1.2.2.1.8.2", "2"),
        ],
        # ifHighSpeed
        "1.3.6.1.2.1.31.1.1.1.15": [
            ("1.3.6.1.2.1.31.1.1.1.15.1", "1000"),
            ("1.3.6.1.2.1.31.1.1.1.15.2", "1000"),
        ],
        # LLDP remTable
        "1.0.8802.1.1.2.1.4.1.1": [],
        # CDP cache
        "1.3.6.1.4.1.9.9.23.1.2.1.1": [],
        # VLAN
        "1.3.6.1.2.1.17.7.1.4.3.1": [],
        # FDB
        "1.3.6.1.2.1.17.7.1.2.2.1": [],
        "1.3.6.1.2.1.17.4.3.1": [],
    }.get(oid, [])

    mock_snmp_cls.return_value = mock_client

    collector = GenericSnmpCollector(probe, creds)
    device, lldp_entries, fdb_entries = collector.collect()

    assert isinstance(device, Device)
    assert device.hostname == "zyxel-sw"
    assert device.vendor == Vendor.ZYXEL
    assert len(device.interfaces) == 2
    assert device.interfaces[0].name == "gi1"


@patch("net_topology.collectors.generic.SnmpClient")
def test_collect_parses_lldp_neighbors(mock_snmp_cls, probe, creds):
    mock_client = MagicMock()

    # Minimal walks — only LLDP has data
    def walk_side_effect(oid):
        if oid == "1.0.8802.1.1.2.1.4.1.1":
            return [
                # lldpRemSysName (index 7)
                ("1.0.8802.1.1.2.1.4.1.1.9.0.1.1", "mikrotik-gw"),
                # lldpRemPortId (index 7)
                ("1.0.8802.1.1.2.1.4.1.1.7.0.1.1", "ether2"),
                # lldpRemChassisId (index 4)
                ("1.0.8802.1.1.2.1.4.1.1.5.0.1.1", "0xaabbccddeeff"),
            ]
        return []

    mock_client.walk.side_effect = walk_side_effect
    mock_snmp_cls.return_value = mock_client

    collector = GenericSnmpCollector(probe, creds)
    device, lldp_entries, fdb_entries = collector.collect()

    assert len(lldp_entries) >= 1
