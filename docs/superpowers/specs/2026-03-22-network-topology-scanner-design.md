# Network Topology Scanner — Design Spec

## Overview

A Python CLI tool (`net-topology`) that automatically discovers network devices, collects inventory data, and maps the physical topology by seeding from a MikroTik router and using SNMP to query all discovered managed devices.

## Equipment Context

- MikroTik router (seed device, RouterOS API + SNMP)
- MikroTik AP (SNMP + RouterOS API)
- Ubiquiti UniFi devices (SNMP)
- Ubiquiti EdgeMAX switch (SNMP)
- Zyxel switch (SNMP)
- ~20-100 total devices on the network

## Architecture

Pipeline: `Seed → Discover → Collect → Link Map → Export`

1. **Seed** — Connect to MikroTik router via RouterOS API. Pull ARP table and LLDP neighbors to bootstrap a list of IPs/MACs.
2. **Discover** — For each discovered IP, probe SNMP (`sysDescr` + `sysName`). Devices that respond are classified as managed; others as endpoints.
3. **Collect** — For each managed device, query SNMP for full inventory (interfaces, LLDP neighbors, VLANs, MAC address table). For MikroTik devices, also query RouterOS API for model + firmware.
4. **Link Map** — Correlate LLDP neighbor data from both sides of each link to build deduplicated port-to-port connections.
5. **Export** — Write structured JSON (or YAML) output.

## Data Model

### Output Structure

```json
{
  "schema_version": "1.0",
  "scan_timestamp": "2026-03-22T15:30:00Z",
  "seed_device": "192.168.1.1",
  "devices": [
    {
      "id": "d-aabbccddeeff",
      "hostname": "mikrotik-gw",
      "ip_addresses": ["192.168.1.1"],
      "mac_addresses": ["AA:BB:CC:DD:EE:FF"],
      "type": "router",
      "vendor": "mikrotik",
      "model": "RB4011",
      "firmware": "RouterOS 7.14",
      "interfaces": [
        {
          "name": "ether1",
          "index": 1,
          "mac": "AA:BB:CC:DD:EE:F0",
          "speed": "1Gbps",
          "status": "up",
          "vlans": [1, 10, 20]
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
      "mac": "11:22:33:44:55:66",
      "hostname": "giacomo-pc",
      "seen_on_device": "zyxel-sw",
      "seen_on_port": "gi12"
    }
  ]
}
```

- **devices** — managed network gear with full inventory
- **links** — port-to-port connections between managed devices (from LLDP)
- **endpoints** — non-managed hosts mapped to the switch port they're seen on

### Device Identity

Each device gets a stable `id` derived from its lowest chassis MAC address (format: `d-<mac_no_colons>`). This prevents duplicates when a device has multiple IPs (e.g., one per VLAN). During discovery, devices are deduplicated by matching on `sysName` + chassis MAC from SNMP response. Links reference devices by `id` rather than hostname to avoid ambiguity.

### Device Type Taxonomy

Devices are classified as one of: `router`, `switch`, `access_point`, `firewall`, `unknown`. Classification is derived from `sysObjectID` and `sysDescr` parsing.

## Project Structure

```
net-topology/
├── config.yaml              # Credentials + seed device config
├── net_topology/
│   ├── __init__.py
│   ├── cli.py               # CLI entry point (argparse)
│   ├── config.py            # Load and validate config.yaml
│   ├── seed.py              # MikroTik RouterOS API — pull ARP + neighbors
│   ├── snmp.py              # SNMP queries — generic wrapper around pysnmp
│   ├── collectors/
│   │   ├── __init__.py
│   │   ├── base.py          # Base collector interface
│   │   ├── generic.py       # Standard MIB collection (sysName, interfaces, LLDP, VLANs)
│   │   └── mikrotik.py      # MikroTik-specific extras via RouterOS API
│   ├── discovery.py         # Probe IPs, classify managed vs endpoint
│   ├── topology.py          # Correlate LLDP data into link map
│   └── export.py            # Write JSON/YAML output
├── requirements.txt
└── pyproject.toml
```

### Dependencies

- `pysnmp` — SNMP v2c/v3 queries
- `routeros-api` — MikroTik RouterOS API
- `pyyaml` — config file parsing + YAML export

## Config File Format

```yaml
seed:
  host: 192.168.1.1
  type: mikrotik
  api:
    username: admin
    password: yourpassword
    port: 8728

discovery_scope:
  - 192.168.1.0/24
  - 10.0.0.0/16

snmp:
  default:
    version: 2c
    community: public
  overrides:  # Most-specific match wins (IP > subnet, smaller subnet > larger)
    - match: 192.168.1.10
      community: private
    - match: 192.168.1.0/24
      version: 3
      security_level: authPriv  # noAuthNoPriv, authNoPriv, or authPriv (inferred from presence of auth/priv fields if omitted)
      username: snmpuser
      auth_protocol: SHA   # SHA or MD5
      auth_password: authpass
      priv_protocol: AES   # AES or DES
      priv_password: privpass

mikrotik_api:
  # Seed device is implicitly included — no need to list it again
  extra_devices:
    - host: 192.168.1.5
  username: admin
  password: yourpassword

output:
  format: json
  file: topology.json

concurrency: 10  # Number of parallel worker threads (default: 10)

logging:
  level: info   # debug, info, warning, error
```

- **seed** — starting device for bootstrapping discovery
- **discovery_scope** — (required) subnets to probe; IPs outside these ranges are ignored. Tool refuses to start without this to prevent accidental WAN probing
- **snmp.default** — default SNMP credentials for all devices
- **snmp.overrides** — per-IP or per-subnet credential overrides; most-specific match wins
- **mikrotik_api** — RouterOS API credentials for MikroTik-specific enrichment; seed device is implicitly included
- **output** — format (json/yaml) and filename
- **logging** — verbosity level; also supports `--verbose`/`--quiet` CLI flags

**Security note:** This file contains plaintext credentials. The tool will warn at startup if the config file is world-readable and recommend `chmod 600`. A `.gitignore` entry for `config.yaml` is generated on init. Environment variable substitution is supported (e.g., `password: ${MIKROTIK_PASSWORD}`) for users who prefer to keep secrets out of the file.

## Discovery & Collection Flow

1. **Load config**, validate credentials are present.
2. **Seed** — connect to MikroTik router via RouterOS API:
   - Pull ARP table → list of (IP, MAC) pairs
   - Pull LLDP neighbors → list of (IP, MAC, platform) of directly connected managed devices
3. **Discovery loop** — for each unique IP found from seed:
   - Skip WAN/public IPs — only probe IPs within configured `discovery_scope` subnets (see config below)
   - Try SNMP `sysDescr` + `sysName` + `sysObjectID` query
   - SNMP responds → **managed device**, deduplicate by chassis MAC, queue for full collection
   - SNMP times out → **endpoint**, record IP/MAC only
   - **Recursive LLDP walk**: when a newly discovered managed device reports LLDP neighbors not yet seen, add those to the discovery queue. This catches devices not in the seed router's ARP table (e.g., switches behind other switches).
4. **Collection** (threaded via `concurrent.futures.ThreadPoolExecutor`, up to 10 workers — chosen because `routeros-api` is synchronous and pysnmp's sync hlapi is simpler; threads avoid needing asyncio wrappers):
   - Generic SNMP collector per managed device:
     - `sysName`, `sysDescr`, `sysObjectID`
     - Interfaces table (`ifTable` / `ifXTable`)
     - LLDP neighbor table (`lldpRemTable`)
     - VLAN table (`dot1qVlanStaticTable`)
     - Bridge FDB / MAC address table
   - MikroTik devices: also query RouterOS API for model + firmware
5. **Topology build** — correlate LLDP entries from both sides into deduplicated links.
6. **Endpoint mapping** — use MAC address tables from switches to map endpoints to ports. When a MAC appears on multiple switches, prefer the switch where it's learned on an access port (not a trunk/uplink) to find the true leaf port. Endpoint hostnames are resolved via reverse DNS lookup (`PTR` record); if no PTR record exists, the hostname is left as `null`.
7. **Export** — write JSON/YAML file (YAML output is structurally identical to JSON).

### Error Handling

- Unreachable devices: log warning, continue scanning
- RouterOS API: 5-second timeout, 2 retries for the seed connection (seed failure is fatal — no scan without it)
- SNMP timeouts: 3-second timeout, 2 retries per device
- Missing LLDP data: link is only recorded if at least one side reports it
- One bad device does not block the scan

### Performance

- 10 concurrent threads via `ThreadPoolExecutor`
- Estimated scan time: 30-90 seconds for 20-100 devices

### LLDP Requirements

LLDP must be enabled on managed devices for topology mapping to work. The tool will:
- Also check for CDP neighbor tables (`cdpCacheTable`) as a fallback for devices that emit CDP instead of LLDP
- Log a warning for any managed device that returns an empty LLDP+CDP table, suggesting the user check if the protocol is enabled
- Report `discovered_via: "lldp"` or `"cdp"` on each link

## Vendor Identification

`sysObjectID` OID prefix mapping:

| OID Prefix | Vendor |
|---|---|
| `1.3.6.1.4.1.14988` | MikroTik |
| `1.3.6.1.4.1.41112` | Ubiquiti (UniFi + EdgeMAX) |
| `1.3.6.1.4.1.890` | Zyxel |

Classification logic:
1. Match `sysObjectID` against known prefixes → set vendor
2. Parse `sysDescr` for model/firmware hints (EdgeMAX includes "EdgeSwitch", UniFi includes "UniFi")
3. MikroTik devices: enrich via RouterOS API if credentials configured
4. Unknown vendors: collect standard MIB data, label vendor as "unknown"
