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
