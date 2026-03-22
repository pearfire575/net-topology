import json
import yaml
import pytest
from datetime import datetime, timezone
from net_topology.export import export_scan
from net_topology.models import ScanResult, Device, DeviceType, Vendor


@pytest.fixture
def scan_result():
    return ScanResult(
        scan_timestamp=datetime(2026, 3, 22, 15, 30, 0, tzinfo=timezone.utc),
        seed_device="192.168.1.1",
        devices=[
            Device(
                hostname="sw1",
                ip_addresses=["192.168.1.2"],
                mac_addresses=["AA:BB:CC:DD:EE:FF"],
                device_type=DeviceType.SWITCH,
                vendor=Vendor.ZYXEL,
            )
        ],
        links=[],
        endpoints=[],
    )


def test_export_json(tmp_path, scan_result):
    out_file = tmp_path / "topology.json"
    export_scan(scan_result, str(out_file), fmt="json")

    data = json.loads(out_file.read_text())
    assert data["schema_version"] == "1.0"
    assert data["seed_device"] == "192.168.1.1"
    assert len(data["devices"]) == 1
    assert data["devices"][0]["hostname"] == "sw1"


def test_export_yaml(tmp_path, scan_result):
    out_file = tmp_path / "topology.yaml"
    export_scan(scan_result, str(out_file), fmt="yaml")

    data = yaml.safe_load(out_file.read_text())
    assert data["schema_version"] == "1.0"
    assert len(data["devices"]) == 1


def test_export_json_is_valid_json(tmp_path, scan_result):
    out_file = tmp_path / "topology.json"
    export_scan(scan_result, str(out_file), fmt="json")
    json.loads(out_file.read_text())


def test_export_unknown_format_raises(tmp_path, scan_result):
    with pytest.raises(ValueError, match="format"):
        export_scan(scan_result, str(tmp_path / "out.txt"), fmt="xml")
