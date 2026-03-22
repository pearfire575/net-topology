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
        if self.mac_addresses:
            lowest = sorted(m.lower().replace(":", "") for m in self.mac_addresses)[0]
            return f"d-{lowest}"
        # Fallback to IP-based ID when no MACs are available
        if self.ip_addresses:
            return f"d-ip-{self.ip_addresses[0].replace('.', '-')}"
        return f"d-{self.hostname}"

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
