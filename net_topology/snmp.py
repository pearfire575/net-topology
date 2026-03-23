from __future__ import annotations

import logging
from dataclasses import dataclass

from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    UsmUserData,
    get_cmd,
    next_cmd,
)
from pysnmp.hlapi.v3arch.asyncio import (
    usmHMACSHAAuthProtocol,
    usmHMACMD5AuthProtocol,
    usmAesCfb128Protocol,
    usmDESPrivProtocol,
)

from net_topology.config import SnmpCredentials

logger = logging.getLogger(__name__)


class SnmpError(Exception):
    pass


OID_SYS_NAME = "1.3.6.1.2.1.1.5.0"
OID_SYS_DESCR = "1.3.6.1.2.1.1.1.0"
OID_SYS_OBJECT_ID = "1.3.6.1.2.1.1.2.0"
OID_IF_TABLE = "1.3.6.1.2.1.2.2.1"
OID_IF_X_TABLE = "1.3.6.1.2.1.31.1.1.1"
OID_LLDP_REM_TABLE = "1.0.8802.1.1.2.1.4.1.1"
OID_CDP_CACHE_TABLE = "1.3.6.1.4.1.9.9.23.1.2.1.1"
OID_DOT1Q_VLAN_STATIC = "1.3.6.1.2.1.17.7.1.4.3.1"
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
    def __init__(self, host: str, credentials: SnmpCredentials, timeout: int = 3, retries: int = 2, port: int = 161):
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
        auth_proto = AUTH_PROTOCOLS.get((creds.auth_protocol or "SHA").upper(), usmHMACSHAAuthProtocol)
        priv_proto = PRIV_PROTOCOLS.get((creds.priv_protocol or "AES").upper(), usmAesCfb128Protocol)
        if creds.auth_password and creds.priv_password:
            return UsmUserData(creds.username or "", creds.auth_password, creds.priv_password, authProtocol=auth_proto, privProtocol=priv_proto)
        elif creds.auth_password:
            return UsmUserData(creds.username or "", creds.auth_password, authProtocol=auth_proto)
        else:
            return UsmUserData(creds.username or "")

    def _build_transport(self):
        return UdpTransportTarget((self.host, self.port), timeout=self.timeout, retries=self.retries)

    async def get(self, *oids: str) -> dict[str, str]:
        object_types = [ObjectType(ObjectIdentity(oid)) for oid in oids]
        error_indication, error_status, error_index, var_binds = await get_cmd(
            self._engine, self._build_auth(), self._build_transport(), ContextData(), *object_types
        )
        if error_indication:
            raise SnmpError(f"SNMP error on {self.host}: {error_indication}")
        if error_status:
            raise SnmpError(f"SNMP error on {self.host}: {error_status.prettyPrint()} at {error_index and var_binds[int(error_index) - 1][0] or '?'}")
        result = {}
        for oid, val in var_binds:
            result[oid.prettyPrint()] = val.prettyPrint()
        return result

    async def walk(self, oid: str) -> list[tuple[str, str]]:
        results = []
        marker = None
        while True:
            target_oid = ObjectType(ObjectIdentity(oid)) if marker is None else marker
            error_indication, error_status, error_index, var_binds = await next_cmd(
                self._engine, self._build_auth(), self._build_transport(), ContextData(),
                target_oid, lexicographicMode=False,
            )
            if error_indication:
                logger.warning("SNMP walk error on %s: %s", self.host, error_indication)
                break
            if error_status:
                logger.warning("SNMP walk error on %s: %s at %s", self.host, error_status.prettyPrint(), error_index)
                break
            if not var_binds:
                break
            for oid_obj, val in var_binds:
                oid_str = oid_obj.prettyPrint()
                if not oid_str.startswith(oid):
                    return results
                results.append((oid_str, val.prettyPrint()))
            marker = var_binds[-1]
        return results

    async def is_reachable(self) -> bool:
        try:
            await self.get(OID_SYS_NAME)
            return True
        except (SnmpError, StopIteration, Exception):
            return False

    async def get_sys_info(self) -> dict[str, str]:
        return await self.get(OID_SYS_NAME, OID_SYS_DESCR, OID_SYS_OBJECT_ID)
