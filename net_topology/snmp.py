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

    def get(self, *oids: str) -> dict[str, str]:
        object_types = [ObjectType(ObjectIdentity(oid)) for oid in oids]
        error_indication, error_status, error_index, var_binds = next(
            getCmd(self._engine, self._build_auth(), self._build_transport(), ContextData(), *object_types)
        )
        if error_indication:
            raise SnmpError(f"SNMP error on {self.host}: {error_indication}")
        if error_status:
            raise SnmpError(f"SNMP error on {self.host}: {error_status.prettyPrint()} at {error_index and var_binds[int(error_index) - 1][0] or '?'}")
        result = {}
        for oid, val in var_binds:
            result[oid.prettyPrint()] = val.prettyPrint()
        return result

    def walk(self, oid: str) -> list[tuple[str, str]]:
        results = []
        for error_indication, error_status, error_index, var_binds in nextCmd(
            self._engine, self._build_auth(), self._build_transport(), ContextData(),
            ObjectType(ObjectIdentity(oid)), lexicographicMode=False,
        ):
            if error_indication:
                logger.warning("SNMP walk error on %s: %s", self.host, error_indication)
                break
            if error_status:
                logger.warning("SNMP walk error on %s: %s at %s", self.host, error_status.prettyPrint(), error_index)
                break
            for oid_obj, val in var_binds:
                results.append((oid_obj.prettyPrint(), val.prettyPrint()))
        return results

    def is_reachable(self) -> bool:
        try:
            self.get(OID_SYS_NAME)
            return True
        except (SnmpError, StopIteration, Exception):
            return False

    def get_sys_info(self) -> dict[str, str]:
        return self.get(OID_SYS_NAME, OID_SYS_DESCR, OID_SYS_OBJECT_ID)
