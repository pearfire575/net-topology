from unittest.mock import patch, MagicMock
import json
import pytest
from net_topology.cli import run_scan


@patch("net_topology.cli.MikrotikCollector")
@patch("net_topology.cli.GenericSnmpCollector")
@patch("net_topology.cli.discover_devices")
@patch("net_topology.cli.MikrotikSeeder")
@patch("net_topology.cli.load_config")
def test_run_scan_full_pipeline(
    mock_load_config,
    mock_seeder_cls,
    mock_discover,
    mock_generic_cls,
    mock_mt_cls,
    tmp_path,
):
    from net_topology.models import Device, DeviceType, Vendor, Interface
    from net_topology.discovery import DeviceProbe
    from net_topology.config import Config
    from ipaddress import IPv4Network

    # Config
    cfg = Config(
        seed_host="192.168.1.1",
        seed_type="mikrotik",
        seed_api_username="admin",
        seed_api_password="pass",
        seed_api_port=8728,
        discovery_networks=[IPv4Network("192.168.1.0/24")],
        snmp_default_version="2c",
        snmp_default_community="public",
        output_format="json",
        output_file=str(tmp_path / "topology.json"),
        concurrency=2,
    )
    mock_load_config.return_value = cfg

    # Seeder
    from net_topology.seed import SeedResult
    mock_seeder = MagicMock()
    mock_seeder.fetch.return_value = SeedResult(
        arp_entries=[("192.168.1.2", "AA:BB:CC:DD:EE:02")],
        lldp_neighbors=[],
    )
    mock_seeder_cls.return_value = mock_seeder

    # Discovery
    mock_discover.return_value = [
        DeviceProbe(
            ip="192.168.1.2",
            mac="AA:BB:CC:DD:EE:02",
            is_managed=True,
            sys_name="zyxel-sw",
            sys_descr="Zyxel GS1920",
            sys_object_id="1.3.6.1.4.1.890.1",
            vendor=Vendor.ZYXEL,
            device_type=DeviceType.SWITCH,
        )
    ]

    # Generic collector
    mock_collector = MagicMock()
    mock_collector.collect.return_value = (
        Device(
            hostname="zyxel-sw",
            ip_addresses=["192.168.1.2"],
            mac_addresses=["AA:BB:CC:DD:EE:02"],
            device_type=DeviceType.SWITCH,
            vendor=Vendor.ZYXEL,
            interfaces=[Interface(name="gi1", index=1, status="up")],
        ),
        [],  # no LLDP
        [],  # no FDB
    )
    mock_generic_cls.return_value = mock_collector

    run_scan(str(tmp_path / "config.yaml"))

    # Verify output was written
    out_file = tmp_path / "topology.json"
    assert out_file.exists()
    data = json.loads(out_file.read_text())
    assert data["schema_version"] == "1.0"
    assert len(data["devices"]) == 1
    assert data["devices"][0]["hostname"] == "zyxel-sw"


@patch("net_topology.cli.load_config")
def test_run_scan_missing_config_raises(mock_load_config):
    from net_topology.config import ConfigError
    mock_load_config.side_effect = ConfigError("Missing 'seed'")
    with pytest.raises(ConfigError):
        run_scan("bad_config.yaml")
