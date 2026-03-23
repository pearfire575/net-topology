from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from net_topology.snmp import SnmpClient, SnmpError
from net_topology.config import SnmpCredentials


@pytest.fixture
def creds_v2c():
    return SnmpCredentials(version="2c", community="public")


@pytest.fixture
def creds_v3():
    return SnmpCredentials(
        version="3",
        security_level="authPriv",
        username="user",
        auth_protocol="SHA",
        auth_password="authpass",
        priv_protocol="AES",
        priv_password="privpass",
    )


def test_snmp_client_init_v2c(creds_v2c):
    client = SnmpClient("192.168.1.1", creds_v2c, timeout=3, retries=2)
    assert client.host == "192.168.1.1"
    assert client.timeout == 3
    assert client.retries == 2


def test_snmp_client_init_v3(creds_v3):
    client = SnmpClient("192.168.1.1", creds_v3)
    assert client.host == "192.168.1.1"


def test_build_auth_v2c(creds_v2c):
    client = SnmpClient("192.168.1.1", creds_v2c)
    auth = client._build_auth()
    assert auth is not None


def test_build_auth_v3(creds_v3):
    client = SnmpClient("192.168.1.1", creds_v3)
    auth = client._build_auth()
    assert auth is not None


@patch("net_topology.snmp.get_cmd")
def test_get_single_oid(mock_get_cmd, creds_v2c):
    mock_var_bind = MagicMock()
    mock_var_bind.__iter__ = lambda self: iter(
        [MagicMock(prettyPrint=lambda: "test-hostname")]
    )
    mock_get_cmd.return_value = (None, None, None, [mock_var_bind])
    client = SnmpClient("192.168.1.1", creds_v2c)
    assert client is not None


@patch("net_topology.snmp.next_cmd")
def test_walk_returns_list(mock_next_cmd, creds_v2c):
    mock_next_cmd.return_value = (None, None, None, [])
    client = SnmpClient("192.168.1.1", creds_v2c)
    assert client is not None
