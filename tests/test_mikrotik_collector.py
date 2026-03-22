from unittest.mock import MagicMock, patch
import pytest
from net_topology.collectors.mikrotik import MikrotikCollector
from net_topology.models import Device, Vendor, DeviceType


@patch("net_topology.collectors.mikrotik.RouterOsApiPool")
def test_enrich_adds_model_and_firmware(mock_pool_cls):
    mock_pool = MagicMock()
    mock_pool_cls.return_value = mock_pool
    mock_api = MagicMock()
    mock_pool.get_api.return_value = mock_api

    resource = MagicMock()
    resource.get.return_value = [
        {
            "board-name": "RB4011iGS+",
            "version": "7.14.1",
            "architecture-name": "arm",
        }
    ]
    mock_api.get_resource.return_value = resource

    device = Device(
        hostname="mikrotik-gw",
        ip_addresses=["192.168.1.1"],
        mac_addresses=["AA:BB:CC:DD:EE:FF"],
        device_type=DeviceType.ROUTER,
        vendor=Vendor.MIKROTIK,
    )

    collector = MikrotikCollector("192.168.1.1", "admin", "pass", port=8728)
    enriched = collector.enrich(device)

    assert enriched.model == "RB4011iGS+"
    assert enriched.firmware == "RouterOS 7.14.1"


@patch("net_topology.collectors.mikrotik.RouterOsApiPool")
def test_enrich_handles_connection_failure(mock_pool_cls):
    mock_pool_cls.side_effect = ConnectionError("refused")

    device = Device(
        hostname="mikrotik-ap",
        ip_addresses=["192.168.1.5"],
        mac_addresses=["AA:BB:CC:DD:EE:00"],
        device_type=DeviceType.ACCESS_POINT,
        vendor=Vendor.MIKROTIK,
    )

    collector = MikrotikCollector("192.168.1.5", "admin", "pass")
    enriched = collector.enrich(device)

    # Should return device unchanged on failure
    assert enriched.model is None
    assert enriched is device
