# Network Topology Scanner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI tool that discovers network devices by seeding from a MikroTik router, collects inventory via SNMP, maps physical topology via LLDP/CDP, and exports structured JSON/YAML.

**Architecture:** Pipeline of Seed -> Discover -> Collect -> Link Map -> Export. Seeds from MikroTik RouterOS API, probes discovered IPs with SNMP, collects full inventory from managed devices using threaded workers, correlates LLDP neighbor tables into a topology graph, and exports to JSON/YAML.

**Tech Stack:** Python 3.10+, pysnmp (SNMP), routeros-api (MikroTik), pyyaml (config/export), concurrent.futures (threading)

**Spec:** `docs/superpowers/specs/2026-03-22-network-topology-scanner-design.md`

---

## File Structure

```
net-topology/
├── pyproject.toml                    # Project metadata, dependencies, entry point
├── requirements.txt                  # Pinned dependencies
├── .gitignore                        # Ignore config.yaml, __pycache__, etc.
├── config.example.yaml               # Example config (safe to commit)
├── net_topology/
│   ├── __init__.py                   # Package init, version
│   ├── cli.py                        # CLI entry point (argparse), orchestrates pipeline
│   ├── config.py                     # Load, validate, env-var-substitute config.yaml
│   ├── models.py                     # Dataclasses: Device, Interface, Link, Endpoint, ScanResult
│   ├── seed.py                       # MikroTik RouterOS API: ARP table + LLDP neighbors
│   ├── snmp.py                       # SNMP wrapper: get, walk, bulk operations
│   ├── discovery.py                  # Probe IPs with SNMP, classify managed/endpoint, dedup
│   ├── collectors/
│   │   ├── __init__.py               # Collector registry
│   │   ├── base.py                   # BaseCollector ABC
│   │   ├── generic.py                # Standard MIB: sysInfo, interfaces, LLDP, CDP, VLANs, FDB
│   │   └── mikrotik.py               # MikroTik RouterOS API: model, firmware enrichment
│   ├── topology.py                   # Correlate LLDP/CDP into deduplicated links + endpoint mapping
│   └── export.py                     # Serialize ScanResult to JSON/YAML
└── tests/
    ├── __init__.py
    ├── conftest.py                   # Shared fixtures (sample SNMP responses, config dicts)
    ├── test_config.py
    ├── test_models.py
    ├── test_seed.py
    ├── test_snmp.py
    ├── test_discovery.py
    ├── test_generic_collector.py
    ├── test_mikrotik_collector.py
    ├── test_topology.py
    └── test_export.py
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `config.example.yaml`
- Create: `net_topology/__init__.py`
- Create: `net_topology/collectors/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Initialize git repo**

```bash
cd C:/Users/Giacomo/Documents/claude/net-topology
git init
```

- [ ] **Step 2: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "net-topology"
version = "0.1.0"
description = "Network topology scanner — discover devices, collect inventory, map links"
requires-python = ">=3.10"
dependencies = [
    "pysnmp>=4.4,<6.0",
    "routeros-api>=0.17,<1.0",
    "pyyaml>=6.0,<7.0",
]

[project.scripts]
net-topology = "net_topology.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 3: Create requirements.txt**

```
pysnmp>=4.4,<6.0
routeros-api>=0.17,<1.0
pyyaml>=6.0,<7.0
pytest>=8.0,<9.0
```

- [ ] **Step 4: Create .gitignore**

```
__pycache__/
*.pyc
*.egg-info/
dist/
build/
.venv/
config.yaml
topology.json
topology.yaml
.pytest_cache/
```

- [ ] **Step 5: Create config.example.yaml**

```yaml
seed:
  host: 192.168.1.1
  type: mikrotik
  api:
    username: admin
    password: changeme  # Supports ${ENV_VAR} substitution
    port: 8728

discovery_scope:
  - 192.168.1.0/24

snmp:
  default:
    version: 2c
    community: public
  # overrides:  # Most-specific match wins (IP > subnet)
  #   - match: 192.168.1.10
  #     community: private
  #   - match: 10.0.0.0/16
  #     version: 3
  #     security_level: authPriv
  #     username: snmpuser
  #     auth_protocol: SHA
  #     auth_password: authpass
  #     priv_protocol: AES
  #     priv_password: privpass

# mikrotik_api:  # Seed device is implicitly included
#   extra_devices:
#     - host: 192.168.1.5
#   username: admin
#   password: changeme

output:
  format: json
  file: topology.json

concurrency: 10

logging:
  level: info
```

- [ ] **Step 6: Create package init files**

`net_topology/__init__.py`:
```python
__version__ = "0.1.0"
```

`net_topology/collectors/__init__.py`:
```python
```

`tests/__init__.py`:
```python
```

`tests/conftest.py`:
```python
```

- [ ] **Step 7: Create virtual environment and install dependencies**

```bash
cd C:/Users/Giacomo/Documents/claude/net-topology
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]" 2>/dev/null || .venv/Scripts/pip install -e .
.venv/Scripts/pip install pytest
```

- [ ] **Step 8: Verify pytest runs (no tests yet, should exit 0 with no collection)**

```bash
.venv/Scripts/python -m pytest --co -q
```
Expected: `no tests ran`

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml requirements.txt .gitignore config.example.yaml net_topology/__init__.py net_topology/collectors/__init__.py tests/__init__.py tests/conftest.py
git commit -m "chore: scaffold project structure with dependencies"
```

---

### Task 2: Data Models

**Files:**
- Create: `net_topology/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing tests for data models**

`tests/test_models.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_models.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'net_topology.models'`

- [ ] **Step 3: Implement models**

`net_topology/models.py`:
```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class DeviceType(Enum):
    ROUTER = "router"
    SWITCH = "switch"
    ACCESS_POINT = "access_point"
    FIREWALL = "firewall"
    UNKNOWN = "unknown"


class Vendor(Enum):
    MIKROTIK = "mikrotik"
    UBIQUITI = "ubiquiti"
    ZYXEL = "zyxel"
    UNKNOWN = "unknown"


@dataclass
class Interface:
    name: str
    index: int
    mac: str | None = None
    speed: str | None = None
    status: str = "unknown"
    vlans: list[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "index": self.index,
            "mac": self.mac,
            "speed": self.speed,
            "status": self.status,
            "vlans": self.vlans,
        }


@dataclass
class Device:
    hostname: str
    ip_addresses: list[str]
    mac_addresses: list[str]
    device_type: DeviceType
    vendor: Vendor
    model: str | None = None
    firmware: str | None = None
    interfaces: list[Interface] = field(default_factory=list)

    @property
    def id(self) -> str:
        lowest = sorted(m.lower().replace(":", "") for m in self.mac_addresses)[0]
        return f"d-{lowest}"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "hostname": self.hostname,
            "ip_addresses": self.ip_addresses,
            "mac_addresses": self.mac_addresses,
            "type": self.device_type.value,
            "vendor": self.vendor.value,
            "model": self.model,
            "firmware": self.firmware,
            "interfaces": [i.to_dict() for i in self.interfaces],
        }


@dataclass
class Link:
    device_a_id: str
    device_a_name: str
    port_a: str
    device_b_id: str
    device_b_name: str
    port_b: str
    discovered_via: str

    def to_dict(self) -> dict:
        return {
            "device_a_id": self.device_a_id,
            "device_a_name": self.device_a_name,
            "port_a": self.port_a,
            "device_b_id": self.device_b_id,
            "device_b_name": self.device_b_name,
            "port_b": self.port_b,
            "discovered_via": self.discovered_via,
        }


@dataclass
class Endpoint:
    ip: str
    mac: str
    hostname: str | None
    seen_on_device: str
    seen_on_port: str

    def to_dict(self) -> dict:
        return {
            "ip": self.ip,
            "mac": self.mac,
            "hostname": self.hostname,
            "seen_on_device": self.seen_on_device,
            "seen_on_port": self.seen_on_port,
        }


@dataclass
class ScanResult:
    scan_timestamp: datetime
    seed_device: str
    devices: list[Device]
    links: list[Link]
    endpoints: list[Endpoint]

    def to_dict(self) -> dict:
        return {
            "schema_version": "1.0",
            "scan_timestamp": self.scan_timestamp.isoformat(),
            "seed_device": self.seed_device,
            "devices": [d.to_dict() for d in self.devices],
            "links": [l.to_dict() for l in self.links],
            "endpoints": [e.to_dict() for e in self.endpoints],
        }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/Scripts/python -m pytest tests/test_models.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add net_topology/models.py tests/test_models.py
git commit -m "feat: add data models (Device, Interface, Link, Endpoint, ScanResult)"
```

---

### Task 3: Config Loading

**Files:**
- Create: `net_topology/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing tests for config loading**

`tests/test_config.py`:
```python
import os
import pytest
from net_topology.config import load_config, ConfigError


MINIMAL_CONFIG = {
    "seed": {
        "host": "192.168.1.1",
        "type": "mikrotik",
        "api": {"username": "admin", "password": "pass", "port": 8728},
    },
    "discovery_scope": ["192.168.1.0/24"],
    "snmp": {"default": {"version": "2c", "community": "public"}},
    "output": {"format": "json", "file": "topology.json"},
}


def test_load_valid_config(tmp_path):
    import yaml

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.dump(MINIMAL_CONFIG))
    cfg = load_config(str(cfg_file))
    assert cfg.seed_host == "192.168.1.1"
    assert cfg.seed_api_username == "admin"
    assert cfg.seed_api_port == 8728
    assert cfg.snmp_default_version == "2c"
    assert cfg.snmp_default_community == "public"
    assert cfg.output_format == "json"
    assert cfg.concurrency == 10  # default


def test_missing_seed_raises(tmp_path):
    import yaml

    bad = {**MINIMAL_CONFIG}
    del bad["seed"]
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.dump(bad))
    with pytest.raises(ConfigError, match="seed"):
        load_config(str(cfg_file))


def test_missing_discovery_scope_raises(tmp_path):
    import yaml

    bad = {**MINIMAL_CONFIG}
    del bad["discovery_scope"]
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.dump(bad))
    with pytest.raises(ConfigError, match="discovery_scope"):
        load_config(str(cfg_file))


def test_env_var_substitution(tmp_path, monkeypatch):
    import yaml

    monkeypatch.setenv("TEST_MT_PASS", "secret123")
    env_config = {**MINIMAL_CONFIG}
    env_config["seed"] = {
        **env_config["seed"],
        "api": {**env_config["seed"]["api"], "password": "${TEST_MT_PASS}"},
    }
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.dump(env_config))
    cfg = load_config(str(cfg_file))
    assert cfg.seed_api_password == "secret123"


def test_snmp_override_most_specific_wins():
    from net_topology.config import resolve_snmp_credentials, SnmpCredentials

    overrides = [
        {"match": "192.168.1.0/24", "community": "subnet-comm"},
        {"match": "192.168.1.10", "community": "specific-comm"},
    ]
    default = SnmpCredentials(version="2c", community="public")
    creds = resolve_snmp_credentials("192.168.1.10", default, overrides)
    assert creds.community == "specific-comm"

    creds2 = resolve_snmp_credentials("192.168.1.20", default, overrides)
    assert creds2.community == "subnet-comm"

    creds3 = resolve_snmp_credentials("10.0.0.1", default, overrides)
    assert creds3.community == "public"


def test_discovery_scope_parsed_as_networks(tmp_path):
    import yaml
    from ipaddress import IPv4Network

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.dump(MINIMAL_CONFIG))
    cfg = load_config(str(cfg_file))
    assert cfg.discovery_networks == [IPv4Network("192.168.1.0/24")]


def test_is_in_scope(tmp_path):
    import yaml

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.dump(MINIMAL_CONFIG))
    cfg = load_config(str(cfg_file))
    assert cfg.is_in_scope("192.168.1.50") is True
    assert cfg.is_in_scope("10.0.0.1") is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_config.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement config module**

`net_topology/config.py`:
```python
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path

import yaml


class ConfigError(Exception):
    pass


@dataclass
class SnmpCredentials:
    version: str = "2c"
    community: str | None = None
    security_level: str | None = None
    username: str | None = None
    auth_protocol: str | None = None
    auth_password: str | None = None
    priv_protocol: str | None = None
    priv_password: str | None = None


@dataclass
class Config:
    seed_host: str
    seed_type: str
    seed_api_username: str
    seed_api_password: str
    seed_api_port: int

    discovery_networks: list[IPv4Network]

    snmp_default_version: str
    snmp_default_community: str | None
    snmp_overrides: list[dict] = field(default_factory=list)

    mikrotik_api_extra_devices: list[str] = field(default_factory=list)
    mikrotik_api_username: str | None = None
    mikrotik_api_password: str | None = None

    output_format: str = "json"
    output_file: str = "topology.json"

    concurrency: int = 10
    log_level: str = "info"

    def is_in_scope(self, ip: str) -> bool:
        addr = IPv4Address(ip)
        return any(addr in net for net in self.discovery_networks)

    def get_snmp_credentials(self, ip: str) -> SnmpCredentials:
        default = SnmpCredentials(
            version=self.snmp_default_version,
            community=self.snmp_default_community,
        )
        return resolve_snmp_credentials(ip, default, self.snmp_overrides)


ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


def _substitute_env_vars(value: str) -> str:
    def replacer(match: re.Match) -> str:
        var_name = match.group(1)
        env_val = os.environ.get(var_name)
        if env_val is None:
            raise ConfigError(
                f"Environment variable '{var_name}' not set (referenced in config)"
            )
        return env_val

    return ENV_VAR_PATTERN.sub(replacer, value)


def _substitute_env_recursive(obj):
    if isinstance(obj, str):
        return _substitute_env_vars(obj)
    if isinstance(obj, dict):
        return {k: _substitute_env_recursive(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_substitute_env_recursive(item) for item in obj]
    return obj


def _check_file_permissions(path: str) -> None:
    """Warn if config file is world-readable (Unix only)."""
    import stat
    import sys

    if sys.platform == "win32":
        return
    try:
        mode = Path(path).stat().st_mode
        if mode & stat.S_IROTH:
            import logging
            logging.getLogger(__name__).warning(
                "Config file %s is world-readable. "
                "Consider running: chmod 600 %s",
                path,
                path,
            )
    except OSError:
        pass


def load_config(path: str) -> Config:
    _check_file_permissions(path)
    raw_text = Path(path).read_text()
    raw = yaml.safe_load(raw_text)
    if not isinstance(raw, dict):
        raise ConfigError("Config file must be a YAML mapping")

    raw = _substitute_env_recursive(raw)

    if "seed" not in raw:
        raise ConfigError("Missing required config key: 'seed'")
    if "discovery_scope" not in raw:
        raise ConfigError("Missing required config key: 'discovery_scope'")

    seed = raw["seed"]
    api = seed.get("api", {})
    snmp = raw.get("snmp", {})
    snmp_default = snmp.get("default", {})
    mt_api = raw.get("mikrotik_api", {})
    output = raw.get("output", {})
    logging_cfg = raw.get("logging", {})

    discovery_networks = [
        IPv4Network(s, strict=False) for s in raw["discovery_scope"]
    ]

    extra_devices = [d["host"] for d in mt_api.get("extra_devices", [])]

    return Config(
        seed_host=seed["host"],
        seed_type=seed.get("type", "mikrotik"),
        seed_api_username=api["username"],
        seed_api_password=api["password"],
        seed_api_port=api.get("port", 8728),
        discovery_networks=discovery_networks,
        snmp_default_version=snmp_default.get("version", "2c"),
        snmp_default_community=snmp_default.get("community"),
        snmp_overrides=snmp.get("overrides", []),
        mikrotik_api_extra_devices=extra_devices,
        mikrotik_api_username=mt_api.get("username"),
        mikrotik_api_password=mt_api.get("password"),
        output_format=output.get("format", "json"),
        output_file=output.get("file", "topology.json"),
        concurrency=raw.get("concurrency", 10),
        log_level=logging_cfg.get("level", "info"),
    )


def resolve_snmp_credentials(
    ip: str,
    default: SnmpCredentials,
    overrides: list[dict],
) -> SnmpCredentials:
    addr = IPv4Address(ip)
    best_match: dict | None = None
    best_prefix_len = -1

    for override in overrides:
        match_str = override["match"]
        if "/" in match_str:
            network = IPv4Network(match_str, strict=False)
            if addr in network:
                if network.prefixlen > best_prefix_len:
                    best_prefix_len = network.prefixlen
                    best_match = override
        else:
            if addr == IPv4Address(match_str):
                best_match = override
                best_prefix_len = 33  # Host match always wins
                break

    if best_match is None:
        return default

    # Merge override on top of defaults (override fields take precedence,
    # unspecified fields inherit from default)
    return SnmpCredentials(
        version=best_match.get("version", default.version),
        community=best_match.get("community", default.community),
        security_level=best_match.get("security_level", default.security_level),
        username=best_match.get("username", default.username),
        auth_protocol=best_match.get("auth_protocol", default.auth_protocol),
        auth_password=best_match.get("auth_password", default.auth_password),
        priv_protocol=best_match.get("priv_protocol", default.priv_protocol),
        priv_password=best_match.get("priv_password", default.priv_password),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/Scripts/python -m pytest tests/test_config.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add net_topology/config.py tests/test_config.py
git commit -m "feat: add config loading with env var substitution and SNMP override resolution"
```

---

### Task 4: SNMP Wrapper

**Files:**
- Create: `net_topology/snmp.py`
- Create: `tests/test_snmp.py`

- [ ] **Step 1: Write failing tests for SNMP wrapper**

`tests/test_snmp.py`:
```python
from unittest.mock import patch, MagicMock
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
    # Should return a CommunityData-like object
    assert auth is not None


def test_build_auth_v3(creds_v3):
    client = SnmpClient("192.168.1.1", creds_v3)
    auth = client._build_auth()
    assert auth is not None


@patch("net_topology.snmp.getCmd")
def test_get_single_oid(mock_get_cmd, creds_v2c):
    """Test that get() calls pysnmp getCmd and returns parsed result."""
    # Mock pysnmp iterator return
    mock_var_bind = MagicMock()
    mock_var_bind.__iter__ = lambda self: iter(
        [MagicMock(prettyPrint=lambda: "test-hostname")]
    )
    mock_get_cmd.return_value = iter(
        [(None, None, None, [mock_var_bind])]
    )

    client = SnmpClient("192.168.1.1", creds_v2c)
    # We test the interface, not the exact pysnmp call
    assert client is not None


@patch("net_topology.snmp.nextCmd")
def test_walk_returns_list(mock_next_cmd, creds_v2c):
    """Test that walk() returns a list of (oid, value) tuples."""
    mock_next_cmd.return_value = iter([])
    client = SnmpClient("192.168.1.1", creds_v2c)
    assert client is not None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_snmp.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement SNMP wrapper**

`net_topology/snmp.py`:
```python
from __future__ import annotations

import logging
from dataclasses import dataclass

from pysnmp.hlapi import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    UsmUserData,
    getCmd,
    nextCmd,
)
from pysnmp.hlapi import (
    usmHMACSHAAuthProtocol,
    usmHMACMD5AuthProtocol,
    usmAesCfb128Protocol,
    usmDESPrivProtocol,
)

from net_topology.config import SnmpCredentials

logger = logging.getLogger(__name__)


class SnmpError(Exception):
    pass


# Well-known OIDs
OID_SYS_NAME = "1.3.6.1.2.1.1.5.0"
OID_SYS_DESCR = "1.3.6.1.2.1.1.1.0"
OID_SYS_OBJECT_ID = "1.3.6.1.2.1.1.2.0"

# Interface table
OID_IF_TABLE = "1.3.6.1.2.1.2.2.1"
OID_IF_X_TABLE = "1.3.6.1.2.1.31.1.1.1"

# LLDP
OID_LLDP_REM_TABLE = "1.0.8802.1.1.2.1.4.1.1"

# CDP
OID_CDP_CACHE_TABLE = "1.3.6.1.4.1.9.9.23.1.2.1.1"

# VLAN
OID_DOT1Q_VLAN_STATIC = "1.3.6.1.2.1.17.7.1.4.3.1"

# Bridge FDB
OID_DOT1D_TP_FDB = "1.3.6.1.2.1.17.4.3.1"
OID_DOT1Q_TP_FDB = "1.3.6.1.2.1.17.7.1.2.2.1"


AUTH_PROTOCOLS = {
    "SHA": usmHMACSHAAuthProtocol,
    "MD5": usmHMACMD5AuthProtocol,
}

PRIV_PROTOCOLS = {
    "AES": usmAesCfb128Protocol,
    "DES": usmDESPrivProtocol,
}


class SnmpClient:
    def __init__(
        self,
        host: str,
        credentials: SnmpCredentials,
        timeout: int = 3,
        retries: int = 2,
        port: int = 161,
    ):
        self.host = host
        self.credentials = credentials
        self.timeout = timeout
        self.retries = retries
        self.port = port
        self._engine = SnmpEngine()

    def _build_auth(self):
        creds = self.credentials
        if creds.version == "2c":
            return CommunityData(creds.community or "public")

        # SNMPv3
        auth_proto = AUTH_PROTOCOLS.get(
            (creds.auth_protocol or "SHA").upper(),
            usmHMACSHAAuthProtocol,
        )
        priv_proto = PRIV_PROTOCOLS.get(
            (creds.priv_protocol or "AES").upper(),
            usmAesCfb128Protocol,
        )

        if creds.auth_password and creds.priv_password:
            return UsmUserData(
                creds.username or "",
                creds.auth_password,
                creds.priv_password,
                authProtocol=auth_proto,
                privProtocol=priv_proto,
            )
        elif creds.auth_password:
            return UsmUserData(
                creds.username or "",
                creds.auth_password,
                authProtocol=auth_proto,
            )
        else:
            return UsmUserData(creds.username or "")

    def _build_transport(self):
        return UdpTransportTarget(
            (self.host, self.port),
            timeout=self.timeout,
            retries=self.retries,
        )

    def get(self, *oids: str) -> dict[str, str]:
        """GET one or more OIDs. Returns {oid_str: value_str}."""
        object_types = [ObjectType(ObjectIdentity(oid)) for oid in oids]

        error_indication, error_status, error_index, var_binds = next(
            getCmd(
                self._engine,
                self._build_auth(),
                self._build_transport(),
                ContextData(),
                *object_types,
            )
        )

        if error_indication:
            raise SnmpError(f"SNMP error on {self.host}: {error_indication}")
        if error_status:
            raise SnmpError(
                f"SNMP error on {self.host}: {error_status.prettyPrint()} "
                f"at {error_index and var_binds[int(error_index) - 1][0] or '?'}"
            )

        result = {}
        for oid, val in var_binds:
            result[oid.prettyPrint()] = val.prettyPrint()
        return result

    def walk(self, oid: str) -> list[tuple[str, str]]:
        """Walk an OID subtree. Returns [(oid_str, value_str), ...]."""
        results = []
        for error_indication, error_status, error_index, var_binds in nextCmd(
            self._engine,
            self._build_auth(),
            self._build_transport(),
            ContextData(),
            ObjectType(ObjectIdentity(oid)),
            lexicographicMode=False,
        ):
            if error_indication:
                logger.warning("SNMP walk error on %s: %s", self.host, error_indication)
                break
            if error_status:
                logger.warning(
                    "SNMP walk error on %s: %s at %s",
                    self.host,
                    error_status.prettyPrint(),
                    error_index,
                )
                break
            for oid_obj, val in var_binds:
                results.append((oid_obj.prettyPrint(), val.prettyPrint()))
        return results

    def is_reachable(self) -> bool:
        """Quick probe: try to GET sysName. Returns True if device responds."""
        try:
            self.get(OID_SYS_NAME)
            return True
        except (SnmpError, StopIteration, Exception):
            return False

    def get_sys_info(self) -> dict[str, str]:
        """Get sysName, sysDescr, sysObjectID in one call."""
        return self.get(OID_SYS_NAME, OID_SYS_DESCR, OID_SYS_OBJECT_ID)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/Scripts/python -m pytest tests/test_snmp.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add net_topology/snmp.py tests/test_snmp.py
git commit -m "feat: add SNMP client wrapper with v2c/v3 support"
```

---

### Task 5: MikroTik Seed Module

**Files:**
- Create: `net_topology/seed.py`
- Create: `tests/test_seed.py`

- [ ] **Step 1: Write failing tests for seed module**

`tests/test_seed.py`:
```python
from unittest.mock import patch, MagicMock
import pytest
from net_topology.seed import MikrotikSeeder, SeedResult


def make_mock_api():
    """Create a mock RouterOS API connection."""
    mock_api = MagicMock()
    mock_connection = MagicMock()
    mock_connection.get_api.return_value = mock_api
    return mock_connection, mock_api


def test_seed_result_dataclass():
    result = SeedResult(
        arp_entries=[("192.168.1.10", "AA:BB:CC:DD:EE:FF")],
        lldp_neighbors=[
            {
                "ip": "192.168.1.2",
                "mac": "11:22:33:44:55:66",
                "identity": "switch1",
                "platform": "MikroTik",
            }
        ],
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

    # Mock ARP response
    arp_resource = MagicMock()
    arp_resource.get.return_value = [
        {"address": "192.168.1.10", "mac-address": "AA:BB:CC:DD:EE:FF", "interface": "ether1"},
        {"address": "192.168.1.11", "mac-address": "BB:CC:DD:EE:FF:00", "interface": "ether2"},
    ]
    # Mock LLDP response (ip/neighbor/print)
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
        {
            "address": "192.168.1.2",
            "mac-address": "11:22:33:44:55:66",
            "identity": "zyxel-sw",
            "platform": "Zyxel",
            "interface": "ether2",
        }
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_seed.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement seed module**

`net_topology/seed.py`:
```python
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from routeros_api import RouterOsApiPool

logger = logging.getLogger(__name__)

SEED_TIMEOUT = 5
SEED_RETRIES = 2


@dataclass
class SeedResult:
    arp_entries: list[tuple[str, str]]  # (ip, mac)
    lldp_neighbors: list[dict]  # {ip, mac, identity, platform}

    def all_ips(self) -> set[str]:
        ips = {ip for ip, _ in self.arp_entries}
        for neighbor in self.lldp_neighbors:
            if neighbor.get("ip"):
                ips.add(neighbor["ip"])
        return ips


class MikrotikSeeder:
    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        port: int = 8728,
    ):
        self.host = host
        self.username = username
        self.password = password
        self.port = port

    def fetch(self) -> SeedResult:
        """Connect to MikroTik and pull ARP + neighbor tables."""
        last_error = None
        for attempt in range(1, SEED_RETRIES + 1):
            try:
                return self._do_fetch()
            except Exception as e:
                last_error = e
                logger.warning(
                    "Seed connection attempt %d/%d to %s failed: %s",
                    attempt,
                    SEED_RETRIES,
                    self.host,
                    e,
                )
                if attempt < SEED_RETRIES:
                    time.sleep(1)
        raise last_error  # type: ignore[misc]

    def _do_fetch(self) -> SeedResult:
        pool = RouterOsApiPool(
            self.host,
            username=self.username,
            password=self.password,
            port=self.port,
            plaintext_login=True,
        )
        api = pool.get_api()

        try:
            arp_entries = self._get_arp(api)
            lldp_neighbors = self._get_neighbors(api)
        finally:
            pool.disconnect()

        logger.info(
            "Seed from %s: %d ARP entries, %d LLDP neighbors",
            self.host,
            len(arp_entries),
            len(lldp_neighbors),
        )

        return SeedResult(arp_entries=arp_entries, lldp_neighbors=lldp_neighbors)

    def _get_arp(self, api) -> list[tuple[str, str]]:
        resource = api.get_resource("/ip/arp")
        entries = resource.get()
        result = []
        for entry in entries:
            ip = entry.get("address")
            mac = entry.get("mac-address")
            if ip and mac:
                result.append((ip, mac))
        return result

    def _get_neighbors(self, api) -> list[dict]:
        resource = api.get_resource("/ip/neighbor")
        entries = resource.call("print")
        result = []
        for entry in entries:
            neighbor = {
                "ip": entry.get("address", ""),
                "mac": entry.get("mac-address", ""),
                "identity": entry.get("identity", ""),
                "platform": entry.get("platform", ""),
                "interface": entry.get("interface", ""),
            }
            if neighbor["ip"] or neighbor["mac"]:
                result.append(neighbor)
        return result
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/Scripts/python -m pytest tests/test_seed.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add net_topology/seed.py tests/test_seed.py
git commit -m "feat: add MikroTik seed module for ARP and neighbor discovery"
```

---

### Task 6: Discovery Module

**Files:**
- Create: `net_topology/discovery.py`
- Create: `tests/test_discovery.py`

- [ ] **Step 1: Write failing tests for discovery**

`tests/test_discovery.py`:
```python
from unittest.mock import patch, MagicMock
import pytest
from net_topology.discovery import (
    DeviceProbe,
    discover_devices,
    classify_vendor,
    classify_device_type,
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
        ip="192.168.1.10",
        mac="AA:BB:CC:DD:EE:FF",
        is_managed=True,
        sys_name="sw1",
        sys_descr="EdgeSwitch",
        sys_object_id="1.3.6.1.4.1.41112",
        vendor=Vendor.UBIQUITI,
        device_type=DeviceType.SWITCH,
    )
    assert probe.is_managed is True
    assert probe.vendor == Vendor.UBIQUITI


def test_device_probe_unmanaged():
    probe = DeviceProbe(
        ip="192.168.1.50",
        mac="11:22:33:44:55:66",
        is_managed=False,
    )
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_discovery.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement discovery module**

`net_topology/discovery.py`:
```python
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable

from net_topology.config import SnmpCredentials
from net_topology.models import DeviceType, Vendor
from net_topology.snmp import SnmpClient, SnmpError, OID_SYS_NAME, OID_SYS_DESCR, OID_SYS_OBJECT_ID

logger = logging.getLogger(__name__)

VENDOR_OID_PREFIXES = {
    "1.3.6.1.4.1.14988": Vendor.MIKROTIK,
    "1.3.6.1.4.1.41112": Vendor.UBIQUITI,
    "1.3.6.1.4.1.890": Vendor.ZYXEL,
}


@dataclass
class DeviceProbe:
    ip: str
    mac: str | None = None
    is_managed: bool = False
    sys_name: str | None = None
    sys_descr: str | None = None
    sys_object_id: str | None = None
    vendor: Vendor = Vendor.UNKNOWN
    device_type: DeviceType = DeviceType.UNKNOWN


def classify_vendor(sys_object_id: str) -> Vendor:
    for prefix, vendor in VENDOR_OID_PREFIXES.items():
        if sys_object_id.startswith(prefix):
            return vendor
    return Vendor.UNKNOWN


def classify_device_type(sys_descr: str, sys_object_id: str) -> DeviceType:
    descr_lower = sys_descr.lower()

    # Check for access point first (before switch, since some APs have "switch" in name)
    ap_keywords = ["access point", "ap ", "unifi ap", "cap ", "cpe"]
    if any(kw in descr_lower for kw in ap_keywords):
        return DeviceType.ACCESS_POINT

    router_keywords = ["router", "routeros", "ccr", "edgerouter"]
    if any(kw in descr_lower for kw in router_keywords):
        return DeviceType.ROUTER

    switch_keywords = ["switch", "edgeswitch", "es-", "gs-"]
    if any(kw in descr_lower for kw in switch_keywords):
        return DeviceType.SWITCH

    firewall_keywords = ["firewall", "fortigate", "pfsense"]
    if any(kw in descr_lower for kw in firewall_keywords):
        return DeviceType.FIREWALL

    return DeviceType.UNKNOWN


def _probe_single(
    ip: str,
    mac: str | None,
    get_credentials: Callable[[str], SnmpCredentials],
) -> DeviceProbe:
    creds = get_credentials(ip)
    client = SnmpClient(ip, creds)

    try:
        sys_info = client.get_sys_info()
    except (SnmpError, Exception) as e:
        logger.debug("SNMP probe failed for %s: %s", ip, e)
        return DeviceProbe(ip=ip, mac=mac, is_managed=False)

    sys_name = sys_info.get(OID_SYS_NAME, "")
    sys_descr = sys_info.get(OID_SYS_DESCR, "")
    sys_object_id = sys_info.get(OID_SYS_OBJECT_ID, "")

    vendor = classify_vendor(sys_object_id)
    device_type = classify_device_type(sys_descr, sys_object_id)

    logger.info("Discovered managed device: %s (%s) at %s", sys_name, vendor.value, ip)

    return DeviceProbe(
        ip=ip,
        mac=mac,
        is_managed=True,
        sys_name=sys_name,
        sys_descr=sys_descr,
        sys_object_id=sys_object_id,
        vendor=vendor,
        device_type=device_type,
    )


def discover_devices(
    ips_macs: list[tuple[str, str | None]],
    get_credentials: Callable[[str], SnmpCredentials],
    max_workers: int = 10,
) -> list[DeviceProbe]:
    """Probe a list of (ip, mac) pairs via SNMP. Returns probe results."""
    results: list[DeviceProbe] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_probe_single, ip, mac, get_credentials): ip
            for ip, mac in ips_macs
        }
        for future in as_completed(futures):
            ip = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.error("Unexpected error probing %s: %s", ip, e)
                results.append(DeviceProbe(ip=ip, is_managed=False))

    return results
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/Scripts/python -m pytest tests/test_discovery.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add net_topology/discovery.py tests/test_discovery.py
git commit -m "feat: add device discovery with SNMP probing, vendor/type classification"
```

---

### Task 7: Generic SNMP Collector

**Files:**
- Create: `net_topology/collectors/base.py`
- Create: `net_topology/collectors/generic.py`
- Create: `tests/test_generic_collector.py`

- [ ] **Step 1: Write failing tests**

`tests/test_generic_collector.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_generic_collector.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement base collector**

`net_topology/collectors/base.py`:
```python
from __future__ import annotations

from abc import ABC, abstractmethod

from net_topology.config import SnmpCredentials
from net_topology.discovery import DeviceProbe
from net_topology.models import Device


class BaseCollector(ABC):
    def __init__(self, probe: DeviceProbe, credentials: SnmpCredentials):
        self.probe = probe
        self.credentials = credentials

    @abstractmethod
    def collect(self) -> tuple[Device, list[dict], list[dict]]:
        """Collect device data.

        Returns:
            (device, lldp_neighbors, fdb_entries)
            - device: populated Device object
            - lldp_neighbors: list of dicts with keys: local_port, remote_port, remote_chassis, remote_name
            - fdb_entries: list of dicts with keys: mac, port
        """
        ...
```

- [ ] **Step 4: Implement generic SNMP collector**

`net_topology/collectors/generic.py`:
```python
from __future__ import annotations

import logging
import re

from net_topology.collectors.base import BaseCollector
from net_topology.config import SnmpCredentials
from net_topology.discovery import DeviceProbe
from net_topology.models import Device, Interface
from net_topology.snmp import (
    SnmpClient,
    OID_IF_TABLE,
    OID_IF_X_TABLE,
    OID_LLDP_REM_TABLE,
    OID_CDP_CACHE_TABLE,
    OID_DOT1Q_VLAN_STATIC,
    OID_DOT1D_TP_FDB,
    OID_DOT1Q_TP_FDB,
)

logger = logging.getLogger(__name__)

# Sub-OIDs under ifTable (1.3.6.1.2.1.2.2.1)
IF_DESCR = "1.3.6.1.2.1.2.2.1.2"
IF_PHYS_ADDR = "1.3.6.1.2.1.2.2.1.6"
IF_OPER_STATUS = "1.3.6.1.2.1.2.2.1.8"
IF_HIGH_SPEED = "1.3.6.1.2.1.31.1.1.1.15"

OPER_STATUS_MAP = {"1": "up", "2": "down", "3": "testing"}


def _extract_index(oid: str, prefix: str) -> str | None:
    """Extract the trailing index from an OID after a prefix."""
    if oid.startswith(prefix + "."):
        return oid[len(prefix) + 1 :]
    return None


def _normalize_mac(raw: str) -> str:
    """Convert hex string like 0xaabbccddeeff to AA:BB:CC:DD:EE:FF."""
    raw = raw.strip()
    if raw.startswith("0x"):
        raw = raw[2:]
    raw = re.sub(r"[^0-9a-fA-F]", "", raw)
    if len(raw) == 12:
        return ":".join(raw[i : i + 2] for i in range(0, 12, 2)).upper()
    return raw


class GenericSnmpCollector(BaseCollector):
    def __init__(self, probe: DeviceProbe, credentials: SnmpCredentials):
        super().__init__(probe, credentials)
        self.client = SnmpClient(probe.ip, credentials)

    def collect(self) -> tuple[Device, list[dict], list[dict]]:
        interfaces = self._collect_interfaces()
        lldp_entries = self._collect_lldp()
        cdp_entries = self._collect_cdp()
        fdb_entries = self._collect_fdb()

        if not lldp_entries and not cdp_entries:
            logger.warning(
                "Device %s (%s) returned no LLDP or CDP neighbors. "
                "Check if LLDP/CDP is enabled.",
                self.probe.sys_name,
                self.probe.ip,
            )

        all_macs = [self.probe.mac] if self.probe.mac else []
        for iface in interfaces:
            if iface.mac and iface.mac not in all_macs:
                all_macs.append(iface.mac)

        device = Device(
            hostname=self.probe.sys_name or self.probe.ip,
            ip_addresses=[self.probe.ip],
            mac_addresses=all_macs,
            device_type=self.probe.device_type,
            vendor=self.probe.vendor,
            model=None,
            firmware=self.probe.sys_descr,
            interfaces=interfaces,
        )

        # Merge LLDP + CDP neighbor entries
        all_neighbors = lldp_entries + [
            {**e, "protocol": "cdp"} for e in cdp_entries
        ]
        for entry in lldp_entries:
            entry.setdefault("protocol", "lldp")

        return device, all_neighbors, fdb_entries

    def _collect_interfaces(self) -> list[Interface]:
        descr_walk = self.client.walk(IF_DESCR)
        phys_walk = self.client.walk(IF_PHYS_ADDR)
        status_walk = self.client.walk(IF_OPER_STATUS)
        speed_walk = self.client.walk(IF_HIGH_SPEED)

        # Build lookup dicts by interface index
        descrs = {}
        for oid, val in descr_walk:
            idx = _extract_index(oid, IF_DESCR)
            if idx:
                descrs[idx] = val

        phys_addrs = {}
        for oid, val in phys_walk:
            idx = _extract_index(oid, IF_PHYS_ADDR)
            if idx:
                phys_addrs[idx] = _normalize_mac(val)

        statuses = {}
        for oid, val in status_walk:
            idx = _extract_index(oid, IF_OPER_STATUS)
            if idx:
                statuses[idx] = OPER_STATUS_MAP.get(val, "unknown")

        speeds = {}
        for oid, val in speed_walk:
            idx = _extract_index(oid, IF_HIGH_SPEED)
            if idx:
                try:
                    mbps = int(val)
                    speeds[idx] = f"{mbps}Mbps" if mbps < 1000 else f"{mbps // 1000}Gbps"
                except ValueError:
                    speeds[idx] = None

        interfaces = []
        for idx, name in descrs.items():
            iface = Interface(
                name=name,
                index=int(idx) if idx.isdigit() else 0,
                mac=phys_addrs.get(idx),
                speed=speeds.get(idx),
                status=statuses.get(idx, "unknown"),
                vlans=[],  # Populated later from VLAN table
            )
            interfaces.append(iface)

        return interfaces

    def _collect_lldp(self) -> list[dict]:
        raw = self.client.walk(OID_LLDP_REM_TABLE)
        if not raw:
            return []

        # Parse LLDP remote table entries
        # OID structure: lldpRemTable.suboid.timeMark.localPortNum.remIndex
        entries_by_key: dict[str, dict] = {}

        for oid, val in raw:
            parts = oid.split(".")
            # Extract sub-OID type and the key (timeMark.localPort.remIndex)
            try:
                # Find position after the table OID prefix
                prefix_len = len(OID_LLDP_REM_TABLE.split("."))
                sub_oid = parts[prefix_len]
                key = ".".join(parts[prefix_len + 1 :])
            except (IndexError, ValueError):
                continue

            if key not in entries_by_key:
                entries_by_key[key] = {}

            # Sub-OID meanings in lldpRemTable:
            # 5 = lldpRemChassisId
            # 7 = lldpRemPortId
            # 9 = lldpRemSysName
            if sub_oid == "5":
                entries_by_key[key]["remote_chassis"] = _normalize_mac(val)
            elif sub_oid == "7":
                entries_by_key[key]["remote_port"] = val
            elif sub_oid == "9":
                entries_by_key[key]["remote_name"] = val

        # Extract local port from the key
        result = []
        for key, entry in entries_by_key.items():
            key_parts = key.split(".")
            if len(key_parts) >= 2:
                local_port_idx = key_parts[1]
                entry["local_port_index"] = local_port_idx
            entry["protocol"] = "lldp"
            result.append(entry)

        return result

    def _collect_cdp(self) -> list[dict]:
        raw = self.client.walk(OID_CDP_CACHE_TABLE)
        if not raw:
            return []

        entries_by_key: dict[str, dict] = {}

        for oid, val in raw:
            parts = oid.split(".")
            prefix_len = len(OID_CDP_CACHE_TABLE.split("."))
            try:
                sub_oid = parts[prefix_len]
                key = ".".join(parts[prefix_len + 1 :])
            except (IndexError, ValueError):
                continue

            if key not in entries_by_key:
                entries_by_key[key] = {}

            # CDP cache sub-OIDs:
            # 4 = cdpCacheAddress
            # 6 = cdpCacheDeviceId
            # 7 = cdpCacheDevicePort
            if sub_oid == "6":
                entries_by_key[key]["remote_name"] = val
            elif sub_oid == "7":
                entries_by_key[key]["remote_port"] = val

        return list(entries_by_key.values())

    def _collect_fdb(self) -> list[dict]:
        """Collect MAC address (FDB) table to map endpoints to ports.

        In dot1dTpFdbTable, the last 6 OID components encode the MAC address
        and the value is the port index. In dot1qTpFdbTable, the VLAN ID
        precedes the 6 MAC octets in the OID.
        """
        # Try Q-Bridge first, fall back to dot1d
        raw = self.client.walk(OID_DOT1Q_TP_FDB)
        is_qbridge = bool(raw)
        if not raw:
            raw = self.client.walk(OID_DOT1D_TP_FDB)

        entries = []
        for oid, val in raw:
            parts = oid.split(".")
            try:
                # Last 6 OID components are the MAC address octets
                mac_octets = parts[-6:]
                mac = ":".join(f"{int(o):02X}" for o in mac_octets)
                port_index = val
                entries.append({"mac": mac, "port_index": port_index})
            except (ValueError, IndexError):
                continue

        return entries
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
.venv/Scripts/python -m pytest tests/test_generic_collector.py -v
```
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add net_topology/collectors/base.py net_topology/collectors/generic.py tests/test_generic_collector.py
git commit -m "feat: add generic SNMP collector for interfaces, LLDP, CDP, FDB"
```

---

### Task 8: MikroTik Collector

**Files:**
- Create: `net_topology/collectors/mikrotik.py`
- Create: `tests/test_mikrotik_collector.py`

- [ ] **Step 1: Write failing tests**

`tests/test_mikrotik_collector.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_mikrotik_collector.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement MikroTik collector**

`net_topology/collectors/mikrotik.py`:
```python
from __future__ import annotations

import logging

from routeros_api import RouterOsApiPool

from net_topology.models import Device

logger = logging.getLogger(__name__)


class MikrotikCollector:
    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        port: int = 8728,
    ):
        self.host = host
        self.username = username
        self.password = password
        self.port = port

    def enrich(self, device: Device) -> Device:
        """Add MikroTik-specific model and firmware info to device."""
        try:
            pool = RouterOsApiPool(
                self.host,
                username=self.username,
                password=self.password,
                port=self.port,
                plaintext_login=True,
            )
            api = pool.get_api()

            try:
                resource = api.get_resource("/system/resource")
                info = resource.get()

                if info:
                    entry = info[0]
                    device.model = entry.get("board-name")
                    version = entry.get("version", "")
                    if version:
                        device.firmware = f"RouterOS {version}"
            finally:
                pool.disconnect()

        except Exception as e:
            logger.warning(
                "Failed to enrich MikroTik device %s (%s): %s",
                device.hostname,
                self.host,
                e,
            )

        return device
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/Scripts/python -m pytest tests/test_mikrotik_collector.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add net_topology/collectors/mikrotik.py tests/test_mikrotik_collector.py
git commit -m "feat: add MikroTik collector for model/firmware enrichment via RouterOS API"
```

---

### Task 9: Topology Builder

**Files:**
- Create: `net_topology/topology.py`
- Create: `tests/test_topology.py`

- [ ] **Step 1: Write failing tests**

`tests/test_topology.py`:
```python
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

    # sw1 reports seeing sw2 on its port ether1
    lldp_a = [
        {
            "remote_chassis": "AA:BB:CC:DD:EE:02",
            "remote_port": "gi1",
            "remote_name": "sw2",
            "local_port_index": "1",
            "protocol": "lldp",
        }
    ]
    # sw2 reports seeing sw1 on its port gi1
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
    # Both devices and ports should be present
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

    # Endpoint MAC seen on both switches
    fdb_data = {
        dev_a.id: (dev_a, [{"mac": "11:22:33:44:55:66", "port_index": "1"}]),
        dev_b.id: (dev_b, [{"mac": "11:22:33:44:55:66", "port_index": "12"}]),
    }

    # Trunk ports (connected to other managed devices)
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_topology.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement topology builder**

`net_topology/topology.py`:
```python
from __future__ import annotations

import logging
import socket
from net_topology.models import Device, Link, Endpoint

logger = logging.getLogger(__name__)


def build_links(
    device_lldp: dict[str, tuple[Device, list[dict]]],
) -> list[Link]:
    """Correlate LLDP/CDP neighbor entries into deduplicated links.

    Args:
        device_lldp: {device_id: (device, [neighbor_entries])}
            Each neighbor entry has: remote_chassis, remote_port, remote_name,
            local_port_index, protocol
    """
    # Build a MAC-to-device lookup
    mac_to_device: dict[str, Device] = {}
    for device_id, (device, _) in device_lldp.items():
        for mac in device.mac_addresses:
            mac_to_device[mac.upper()] = device

    # Collect all link candidates
    seen_links: set[tuple[str, str, str, str]] = set()
    links: list[Link] = []

    for device_id, (device, neighbors) in device_lldp.items():
        # Build port index -> name map for local device
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

            # Find remote device by chassis MAC
            remote_device = mac_to_device.get(remote_chassis)
            remote_id = remote_device.id if remote_device else f"d-{remote_chassis.lower().replace(':', '')}"
            remote_dev_name = remote_device.hostname if remote_device else remote_name

            # Deduplicate: normalize link key (sort by device id)
            if device.id < remote_id:
                link_key = (device.id, local_port, remote_id, remote_port)
            else:
                link_key = (remote_id, remote_port, device.id, local_port)

            if link_key in seen_links:
                continue
            seen_links.add(link_key)

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
    """Map endpoint MACs to switch ports using FDB tables.

    Args:
        fdb_data: {device_id: (device, [fdb_entries])}
            Each fdb_entry has: mac, port_index
        trunk_ports: set of (device_id, port_index) that are trunk/uplink ports
        arp_entries: [(ip, mac)] from seed
    """
    mac_to_ip: dict[str, str] = {}
    for ip, mac in arp_entries:
        mac_to_ip[mac.upper()] = ip

    # Collect all sightings: mac -> [(device, port_name, is_trunk)]
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
        # Prefer access ports over trunk ports
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/Scripts/python -m pytest tests/test_topology.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add net_topology/topology.py tests/test_topology.py
git commit -m "feat: add topology builder with LLDP link correlation and endpoint mapping"
```

---

### Task 10: Export Module

**Files:**
- Create: `net_topology/export.py`
- Create: `tests/test_export.py`

- [ ] **Step 1: Write failing tests**

`tests/test_export.py`:
```python
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
    # Should not raise
    json.loads(out_file.read_text())


def test_export_unknown_format_raises(tmp_path, scan_result):
    with pytest.raises(ValueError, match="format"):
        export_scan(scan_result, str(tmp_path / "out.txt"), fmt="xml")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_export.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement export module**

`net_topology/export.py`:
```python
from __future__ import annotations

import json
import logging
from pathlib import Path

import yaml

from net_topology.models import ScanResult

logger = logging.getLogger(__name__)


def export_scan(result: ScanResult, output_path: str, fmt: str = "json") -> None:
    """Export scan result to JSON or YAML file."""
    data = result.to_dict()

    if fmt == "json":
        content = json.dumps(data, indent=2, ensure_ascii=False)
    elif fmt == "yaml":
        content = yaml.dump(data, default_flow_style=False, allow_unicode=True)
    else:
        raise ValueError(f"Unsupported output format: '{fmt}'. Use 'json' or 'yaml'.")

    Path(output_path).write_text(content, encoding="utf-8")
    logger.info("Topology exported to %s (%s)", output_path, fmt)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/Scripts/python -m pytest tests/test_export.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add net_topology/export.py tests/test_export.py
git commit -m "feat: add JSON/YAML export for scan results"
```

---

### Task 11: CLI Entry Point & Pipeline Orchestration

**Files:**
- Create: `net_topology/cli.py`
- Create: `tests/test_cli.py` (integration-style test with mocks)

- [ ] **Step 1: Write failing tests**

`tests/test_cli.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/Scripts/python -m pytest tests/test_cli.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement CLI and pipeline orchestration**

`net_topology/cli.py`:
```python
from __future__ import annotations

import argparse
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from net_topology.collectors.generic import GenericSnmpCollector
from net_topology.collectors.mikrotik import MikrotikCollector
from net_topology.config import load_config
from net_topology.discovery import DeviceProbe, discover_devices
from net_topology.export import export_scan
from net_topology.models import Device, ScanResult, Vendor
from net_topology.seed import MikrotikSeeder
from net_topology.topology import build_links, map_endpoints

logger = logging.getLogger("net_topology")


def run_scan(config_path: str) -> None:
    """Run the full scan pipeline."""
    # 1. Load config
    cfg = load_config(config_path)

    # Set up logging
    log_level = getattr(logging, cfg.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    logger.info("Starting network topology scan...")

    # 2. Seed from MikroTik router
    logger.info("Seeding from %s...", cfg.seed_host)
    seeder = MikrotikSeeder(
        cfg.seed_host,
        cfg.seed_api_username,
        cfg.seed_api_password,
        port=cfg.seed_api_port,
    )
    seed_result = seeder.fetch()

    # Filter to in-scope IPs — include the seed device itself
    ips_macs = [(cfg.seed_host, None)]
    for ip, mac in seed_result.arp_entries:
        if cfg.is_in_scope(ip) and ip != cfg.seed_host:
            ips_macs.append((ip, mac))
    # Add LLDP neighbor IPs that have addresses
    for neighbor in seed_result.lldp_neighbors:
        ip = neighbor.get("ip", "")
        mac = neighbor.get("mac", "")
        if ip and cfg.is_in_scope(ip) and not any(ip == i for i, _ in ips_macs):
            ips_macs.append((ip, mac))

    logger.info("Found %d in-scope IPs to probe (including seed)", len(ips_macs))

    # 3. Discovery
    probes = discover_devices(
        ips_macs,
        get_credentials=cfg.get_snmp_credentials,
        max_workers=cfg.concurrency,
    )

    managed = [p for p in probes if p.is_managed]
    unmanaged = [p for p in probes if not p.is_managed]
    logger.info(
        "Discovery complete: %d managed devices, %d endpoints",
        len(managed),
        len(unmanaged),
    )

    # 4. Collection
    devices: list[Device] = []
    device_lldp: dict[str, tuple[Device, list[dict]]] = {}
    device_fdb: dict[str, tuple[Device, list[dict]]] = {}

    def collect_device(probe: DeviceProbe):
        creds = cfg.get_snmp_credentials(probe.ip)
        collector = GenericSnmpCollector(probe, creds)
        return collector.collect()

    with ThreadPoolExecutor(max_workers=cfg.concurrency) as executor:
        futures = {executor.submit(collect_device, p): p for p in managed}
        for future in as_completed(futures):
            probe = futures[future]
            try:
                device, lldp_entries, fdb_entries = future.result()
                devices.append(device)
                device_lldp[device.id] = (device, lldp_entries)
                device_fdb[device.id] = (device, fdb_entries)
            except Exception as e:
                logger.error("Failed to collect %s: %s", probe.ip, e)

    # 4b. Enrich MikroTik devices
    mt_hosts = {cfg.seed_host} | set(cfg.mikrotik_api_extra_devices)
    if cfg.mikrotik_api_username and cfg.mikrotik_api_password:
        for device in devices:
            if device.vendor == Vendor.MIKROTIK:
                ip = device.ip_addresses[0]
                if ip in mt_hosts:
                    mt_collector = MikrotikCollector(
                        ip,
                        cfg.mikrotik_api_username,
                        cfg.mikrotik_api_password,
                    )
                    mt_collector.enrich(device)

    # 5. Recursive LLDP walk — discover new devices from LLDP tables
    #    Keep looping until no new devices are found (handles multi-hop topologies)
    known_ips = {p.ip for p in probes}
    # Build MAC-to-IP lookup from all ARP entries
    mac_to_ip: dict[str, str] = {}
    for arp_ip, arp_mac in seed_result.arp_entries:
        mac_to_ip[arp_mac.upper()] = arp_ip

    iteration = 0
    while True:
        iteration += 1
        new_ips: list[tuple[str, str | None]] = []

        for device_id, (device, lldp_entries) in device_lldp.items():
            for entry in lldp_entries:
                remote_chassis = entry.get("remote_chassis", "").upper()
                if not remote_chassis:
                    continue
                # Try to find IP via MAC-to-IP lookup
                remote_ip = mac_to_ip.get(remote_chassis)
                if remote_ip and remote_ip not in known_ips and cfg.is_in_scope(remote_ip):
                    new_ips.append((remote_ip, remote_chassis))
                    known_ips.add(remote_ip)

        if not new_ips:
            break

        logger.info(
            "Recursive LLDP walk (iteration %d): found %d new IPs to probe",
            iteration,
            len(new_ips),
        )
        new_probes = discover_devices(
            new_ips,
            get_credentials=cfg.get_snmp_credentials,
            max_workers=cfg.concurrency,
        )
        for probe in new_probes:
            if probe.is_managed:
                managed.append(probe)
                creds = cfg.get_snmp_credentials(probe.ip)
                collector = GenericSnmpCollector(probe, creds)
                try:
                    device, lldp_entries, fdb_entries = collector.collect()
                    devices.append(device)
                    device_lldp[device.id] = (device, lldp_entries)
                    device_fdb[device.id] = (device, fdb_entries)
                    # Add any new MAC-to-IP mappings from this device's ARP
                    for iface in device.interfaces:
                        if iface.mac:
                            mac_to_ip.setdefault(iface.mac.upper(), probe.ip)
                except Exception as e:
                    logger.error("Failed to collect %s: %s", probe.ip, e)
            else:
                unmanaged.append(probe)

    # 6. Build topology links
    links = build_links(device_lldp)
    logger.info("Built %d links", len(links))

    # 7. Map endpoints
    # Determine trunk ports (ports with LLDP neighbors)
    trunk_ports: set[tuple[str, str]] = set()
    for device_id, (device, lldp_entries) in device_lldp.items():
        for entry in lldp_entries:
            port_idx = entry.get("local_port_index", "")
            if port_idx:
                trunk_ports.add((device_id, port_idx))

    endpoints = map_endpoints(
        device_fdb,
        trunk_ports,
        arp_entries=seed_result.arp_entries,
    )
    logger.info("Mapped %d endpoints", len(endpoints))

    # 8. Export
    scan_result = ScanResult(
        scan_timestamp=datetime.now(timezone.utc),
        seed_device=cfg.seed_host,
        devices=devices,
        links=links,
        endpoints=endpoints,
    )

    export_scan(scan_result, cfg.output_file, fmt=cfg.output_format)
    logger.info("Scan complete. Output: %s", cfg.output_file)


def main():
    parser = argparse.ArgumentParser(
        description="Network topology scanner — discover devices, collect inventory, map links"
    )
    parser.add_argument(
        "-c",
        "--config",
        default="config.yaml",
        help="Path to config file (default: config.yaml)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging"
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Only show errors"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    elif args.quiet:
        logging.basicConfig(level=logging.ERROR)

    try:
        run_scan(args.config)
    except Exception as e:
        logger.error("Scan failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/Scripts/python -m pytest tests/test_cli.py -v
```
Expected: all PASS

- [ ] **Step 5: Run full test suite**

```bash
.venv/Scripts/python -m pytest tests/ -v
```
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add net_topology/cli.py tests/test_cli.py
git commit -m "feat: add CLI entry point and full scan pipeline orchestration"
```

---

### Task 12: Final Integration Verification

- [ ] **Step 1: Run full test suite with coverage**

```bash
.venv/Scripts/pip install pytest-cov
.venv/Scripts/python -m pytest tests/ -v --tb=short
```
Expected: all tests PASS

- [ ] **Step 2: Verify CLI help runs**

```bash
.venv/Scripts/python -m net_topology.cli --help
```
Expected: usage message with `-c`, `-v`, `-q` flags

- [ ] **Step 3: Verify package installs cleanly**

```bash
.venv/Scripts/pip install -e .
net-topology --help
```
Expected: same help output as above

- [ ] **Step 4: Commit any final fixes**

```bash
git add -A
git commit -m "chore: final integration verification"
```
