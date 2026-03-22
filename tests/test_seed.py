from unittest.mock import patch, MagicMock
import pytest
from net_topology.seed import MikrotikSeeder, SeedResult


def make_mock_api():
    mock_api = MagicMock()
    mock_connection = MagicMock()
    mock_connection.get_api.return_value = mock_api
    return mock_connection, mock_api


def test_seed_result_dataclass():
    result = SeedResult(
        arp_entries=[("192.168.1.10", "AA:BB:CC:DD:EE:FF")],
        lldp_neighbors=[{"ip": "192.168.1.2", "mac": "11:22:33:44:55:66", "identity": "switch1", "platform": "MikroTik"}],
    )
    assert len(result.arp_entries) == 1
    assert len(result.lldp_neighbors) == 1
    assert result.all_ips() == {"192.168.1.10", "192.168.1.2"}


@patch("net_topology.seed.RouterOsApiPool")
def test_seeder_fetches_arp(mock_pool_cls):
    mock_pool = MagicMock()
    mock_pool_cls.return_value = mock_pool
    mock_api = MagicMock()
    mock_pool.get_api.return_value = mock_api
    arp_resource = MagicMock()
    arp_resource.get.return_value = [
        {"address": "192.168.1.10", "mac-address": "AA:BB:CC:DD:EE:FF", "interface": "ether1"},
        {"address": "192.168.1.11", "mac-address": "BB:CC:DD:EE:FF:00", "interface": "ether2"},
    ]
    lldp_resource = MagicMock()
    lldp_resource.call.return_value = []
    def get_resource(path):
        r = MagicMock()
        if path == "/ip/arp":
            r.get.return_value = arp_resource.get.return_value
            return r
        if path == "/ip/neighbor":
            r.call.return_value = lldp_resource.call.return_value
            return r
        return r
    mock_api.get_resource.side_effect = get_resource
    seeder = MikrotikSeeder("192.168.1.1", "admin", "pass", port=8728)
    result = seeder.fetch()
    assert ("192.168.1.10", "AA:BB:CC:DD:EE:FF") in result.arp_entries
    assert ("192.168.1.11", "BB:CC:DD:EE:FF:00") in result.arp_entries


@patch("net_topology.seed.RouterOsApiPool")
def test_seeder_fetches_lldp_neighbors(mock_pool_cls):
    mock_pool = MagicMock()
    mock_pool_cls.return_value = mock_pool
    mock_api = MagicMock()
    mock_pool.get_api.return_value = mock_api
    arp_resource = MagicMock()
    arp_resource.get.return_value = []
    lldp_resource = MagicMock()
    lldp_resource.call.return_value = [
        {"address": "192.168.1.2", "mac-address": "11:22:33:44:55:66", "identity": "zyxel-sw", "platform": "Zyxel", "interface": "ether2"}
    ]
    def get_resource(path):
        r = MagicMock()
        if path == "/ip/arp":
            r.get.return_value = arp_resource.get.return_value
            return r
        if path == "/ip/neighbor":
            r.call.return_value = lldp_resource.call.return_value
            return r
        return r
    mock_api.get_resource.side_effect = get_resource
    seeder = MikrotikSeeder("192.168.1.1", "admin", "pass", port=8728)
    result = seeder.fetch()
    assert len(result.lldp_neighbors) == 1
    assert result.lldp_neighbors[0]["ip"] == "192.168.1.2"
    assert result.lldp_neighbors[0]["identity"] == "zyxel-sw"


@patch("net_topology.seed.RouterOsApiPool")
def test_seeder_connection_failure_raises(mock_pool_cls):
    mock_pool_cls.side_effect = ConnectionError("Connection refused")
    seeder = MikrotikSeeder("192.168.1.1", "admin", "pass", port=8728)
    with pytest.raises(ConnectionError):
        seeder.fetch()
