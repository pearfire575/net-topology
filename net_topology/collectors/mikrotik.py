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
