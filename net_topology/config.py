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
    import stat
    import sys
    if sys.platform == "win32":
        return
    try:
        mode = Path(path).stat().st_mode
        if mode & stat.S_IROTH:
            import logging
            logging.getLogger(__name__).warning(
                "Config file %s is world-readable. Consider running: chmod 600 %s",
                path, path,
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
    discovery_networks = [IPv4Network(s, strict=False) for s in raw["discovery_scope"]]
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
                best_prefix_len = 33
                break
    if best_match is None:
        return default
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
