# net-topology

A Python CLI tool that automatically discovers network devices, collects inventory data, and maps physical topology via SNMP and the MikroTik RouterOS API.

## What it does

1. **Seeds** from a MikroTik router — pulls the ARP table and LLDP neighbor list
2. **Discovers** all reachable devices in scope via SNMP (`sysName`, `sysDescr`, `sysObjectID`)
3. **Classifies** each device by vendor (MikroTik, Ubiquiti, Zyxel) and type (router, switch, AP)
4. **Collects** per-device data: interfaces, LLDP/CDP neighbors, MAC address tables (FDB)
5. **Enriches** MikroTik devices with model and firmware via the RouterOS API
6. **Recursively walks** LLDP tables to discover multi-hop neighbors
7. **Builds** deduplicated topology links from correlated LLDP/CDP data
8. **Maps** endpoints (PCs, phones, etc.) to switch ports using FDB + ARP
9. **Exports** everything to structured JSON or YAML

## Supported devices

| Vendor   | Discovery | Inventory | Topology | Enrichment |
|----------|-----------|-----------|----------|------------|
| MikroTik | SNMP      | SNMP      | LLDP     | RouterOS API (model, firmware) |
| Ubiquiti | SNMP      | SNMP      | LLDP/CDP | —          |
| Zyxel    | SNMP      | SNMP      | LLDP     | —          |
| Other    | SNMP      | SNMP      | LLDP/CDP | —          |

## Installation

```bash
python -m venv .venv
.venv/Scripts/activate   # Windows
# source .venv/bin/activate  # Linux/macOS

pip install -e .
```

## Configuration

Copy the example config and fill in your credentials:

```bash
cp config.example.yaml config.yaml
```

```yaml
seed:
  host: 192.168.1.1
  type: mikrotik
  api:
    username: admin
    password: ${ROUTER_PASSWORD}  # env var substitution supported
    port: 8728

discovery_scope:
  - 192.168.1.0/24

snmp:
  default:
    version: 2c
    community: public
  overrides:  # most-specific match wins (IP > subnet > default)
    - match: 192.168.1.10
      community: private
    - match: 10.0.0.0/16
      version: 3
      security_level: authPriv
      username: snmpuser
      auth_protocol: SHA
      auth_password: authpass
      priv_protocol: AES
      priv_password: privpass

mikrotik_api:  # optional — enriches MikroTik devices with model/firmware
  extra_devices:
    - host: 192.168.1.5
  username: admin
  password: ${ROUTER_PASSWORD}

output:
  format: json   # json or yaml
  file: topology.json

concurrency: 10

logging:
  level: info    # debug, info, warning, error
```

Credentials support `${ENV_VAR}` substitution so you don't have to put passwords in the file.

## Usage

```bash
# Default: reads config.yaml, writes topology.json
net-topology

# Custom config path
net-topology -c /path/to/config.yaml

# Verbose (debug) logging
net-topology -v

# Quiet (errors only)
net-topology -q
```

## Output schema

The output file contains a JSON/YAML document with `schema_version: "1.0"`:

```json
{
  "schema_version": "1.0",
  "scan_timestamp": "2026-03-22T15:30:00+00:00",
  "seed_device": "192.168.1.1",
  "devices": [
    {
      "id": "d-aabbccddeeff",
      "hostname": "mikrotik-gw",
      "ip_addresses": ["192.168.1.1"],
      "mac_addresses": ["AA:BB:CC:DD:EE:FF"],
      "device_type": "router",
      "vendor": "mikrotik",
      "model": "RB4011iGS+",
      "firmware": "RouterOS 7.14.1",
      "interfaces": [
        {
          "name": "ether1",
          "index": 1,
          "mac": "AA:BB:CC:DD:EE:F0",
          "speed": "1Gbps",
          "status": "up",
          "vlans": []
        }
      ]
    }
  ],
  "links": [
    {
      "device_a_id": "d-aabbccddeeff",
      "device_a_name": "mikrotik-gw",
      "port_a": "ether2",
      "device_b_id": "d-112233445566",
      "device_b_name": "zyxel-sw",
      "port_b": "gi1",
      "discovered_via": "lldp"
    }
  ],
  "endpoints": [
    {
      "ip": "192.168.1.50",
      "mac": "DE:AD:BE:EF:00:01",
      "hostname": "giacomo-pc.local",
      "seen_on_device": "zyxel-sw",
      "seen_on_port": "gi12"
    }
  ]
}
```

## Prerequisites on network devices

- **SNMP**: Enable SNMPv2c or v3 on all managed devices with a community/credentials matching your config
- **LLDP**: Enable LLDP on all switches and routers for topology link discovery
- **MikroTik API**: Enable the API service on MikroTik devices (port 8728 by default)

## Development

```bash
pip install -r requirements.txt

# Run tests
python -m pytest tests/ -v

# Run a single test file
python -m pytest tests/test_topology.py -v
```

## Project structure

```
net_topology/
  __init__.py          # version
  cli.py               # CLI entry point and scan pipeline
  config.py            # YAML config loading, env var substitution, SNMP credential resolution
  discovery.py         # SNMP-based device discovery, vendor/type classification
  export.py            # JSON/YAML export
  models.py            # Device, Interface, Link, Endpoint, ScanResult dataclasses
  seed.py              # MikroTik RouterOS API seeder (ARP + LLDP)
  snmp.py              # pysnmp wrapper (get, walk, SNMPv2c/v3 auth)
  topology.py          # LLDP link correlation, FDB endpoint mapping
  collectors/
    base.py            # BaseCollector ABC
    generic.py         # SNMP collector (interfaces, LLDP, CDP, FDB)
    mikrotik.py        # RouterOS API enrichment (model, firmware)
```
