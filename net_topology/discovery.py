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

def _probe_single(ip: str, mac: str | None, get_credentials: Callable[[str], SnmpCredentials]) -> DeviceProbe:
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
    return DeviceProbe(ip=ip, mac=mac, is_managed=True, sys_name=sys_name, sys_descr=sys_descr, sys_object_id=sys_object_id, vendor=vendor, device_type=device_type)

def discover_devices(ips_macs: list[tuple[str, str | None]], get_credentials: Callable[[str], SnmpCredentials], max_workers: int = 10) -> list[DeviceProbe]:
    results: list[DeviceProbe] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_probe_single, ip, mac, get_credentials): ip for ip, mac in ips_macs}
        for future in as_completed(futures):
            ip = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.error("Unexpected error probing %s: %s", ip, e)
                results.append(DeviceProbe(ip=ip, is_managed=False))
    return results
