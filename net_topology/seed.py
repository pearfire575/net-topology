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
    arp_entries: list[tuple[str, str]]
    lldp_neighbors: list[dict]

    def all_ips(self) -> set[str]:
        ips = {ip for ip, _ in self.arp_entries}
        for neighbor in self.lldp_neighbors:
            if neighbor.get("ip"):
                ips.add(neighbor["ip"])
        return ips


class MikrotikSeeder:
    def __init__(self, host: str, username: str, password: str, port: int = 8728):
        self.host = host
        self.username = username
        self.password = password
        self.port = port

    def fetch(self) -> SeedResult:
        last_error = None
        for attempt in range(1, SEED_RETRIES + 1):
            try:
                return self._do_fetch()
            except Exception as e:
                last_error = e
                logger.warning("Seed connection attempt %d/%d to %s failed: %s", attempt, SEED_RETRIES, self.host, e)
                if attempt < SEED_RETRIES:
                    time.sleep(1)
        raise last_error

    def _do_fetch(self) -> SeedResult:
        pool = RouterOsApiPool(self.host, username=self.username, password=self.password, port=self.port, plaintext_login=True)
        api = pool.get_api()
        try:
            arp_entries = self._get_arp(api)
            lldp_neighbors = self._get_neighbors(api)
        finally:
            pool.disconnect()
        logger.info("Seed from %s: %d ARP entries, %d LLDP neighbors", self.host, len(arp_entries), len(lldp_neighbors))
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
