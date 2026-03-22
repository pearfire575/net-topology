from __future__ import annotations

import argparse
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from net_topology.collectors.generic import GenericSnmpCollector
from net_topology.collectors.mikrotik import MikrotikCollector
from net_topology.config import load_config
from net_topology.discovery import DeviceProbe, discover_devices
from net_topology.export import export_scan
from net_topology.models import Device, ScanResult, Vendor
from net_topology.seed import MikrotikSeeder
from net_topology.topology import build_links, map_endpoints

logger = logging.getLogger("net_topology")


def run_scan(config_path: str) -> None:
    """Run the full scan pipeline."""
    # 1. Load config
    cfg = load_config(config_path)

    # Set up logging
    log_level = getattr(logging, cfg.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    logger.info("Starting network topology scan...")

    # 2. Seed from MikroTik router
    logger.info("Seeding from %s...", cfg.seed_host)
    seeder = MikrotikSeeder(
        cfg.seed_host,
        cfg.seed_api_username,
        cfg.seed_api_password,
        port=cfg.seed_api_port,
    )
    seed_result = seeder.fetch()

    # Filter to in-scope IPs — include the seed device itself
    ips_macs = [(cfg.seed_host, None)]
    for ip, mac in seed_result.arp_entries:
        if cfg.is_in_scope(ip) and ip != cfg.seed_host:
            ips_macs.append((ip, mac))
    # Add LLDP neighbor IPs that have addresses
    for neighbor in seed_result.lldp_neighbors:
        ip = neighbor.get("ip", "")
        mac = neighbor.get("mac", "")
        if ip and cfg.is_in_scope(ip) and not any(ip == i for i, _ in ips_macs):
            ips_macs.append((ip, mac))

    logger.info("Found %d in-scope IPs to probe (including seed)", len(ips_macs))

    # 3. Discovery
    probes = discover_devices(
        ips_macs,
        get_credentials=cfg.get_snmp_credentials,
        max_workers=cfg.concurrency,
    )

    managed = [p for p in probes if p.is_managed]
    unmanaged = [p for p in probes if not p.is_managed]
    logger.info(
        "Discovery complete: %d managed devices, %d endpoints",
        len(managed),
        len(unmanaged),
    )

    # 4. Collection
    devices: list[Device] = []
    device_lldp: dict[str, tuple[Device, list[dict]]] = {}
    device_fdb: dict[str, tuple[Device, list[dict]]] = {}

    def collect_device(probe: DeviceProbe):
        creds = cfg.get_snmp_credentials(probe.ip)
        collector = GenericSnmpCollector(probe, creds)
        return collector.collect()

    with ThreadPoolExecutor(max_workers=cfg.concurrency) as executor:
        futures = {executor.submit(collect_device, p): p for p in managed}
        for future in as_completed(futures):
            probe = futures[future]
            try:
                device, lldp_entries, fdb_entries = future.result()
                devices.append(device)
                device_lldp[device.id] = (device, lldp_entries)
                device_fdb[device.id] = (device, fdb_entries)
            except Exception as e:
                logger.error("Failed to collect %s: %s", probe.ip, e)

    # 4b. Enrich MikroTik devices
    mt_hosts = {cfg.seed_host} | set(cfg.mikrotik_api_extra_devices)
    if cfg.mikrotik_api_username and cfg.mikrotik_api_password:
        for device in devices:
            if device.vendor == Vendor.MIKROTIK:
                ip = device.ip_addresses[0]
                if ip in mt_hosts:
                    mt_collector = MikrotikCollector(
                        ip,
                        cfg.mikrotik_api_username,
                        cfg.mikrotik_api_password,
                    )
                    mt_collector.enrich(device)

    # 5. Recursive LLDP walk — discover new devices from LLDP tables
    known_ips = {p.ip for p in probes}
    mac_to_ip: dict[str, str] = {}
    for arp_ip, arp_mac in seed_result.arp_entries:
        mac_to_ip[arp_mac.upper()] = arp_ip

    iteration = 0
    while True:
        iteration += 1
        new_ips: list[tuple[str, str | None]] = []

        for device_id, (device, lldp_entries) in device_lldp.items():
            for entry in lldp_entries:
                remote_chassis = entry.get("remote_chassis", "").upper()
                if not remote_chassis:
                    continue
                remote_ip = mac_to_ip.get(remote_chassis)
                if remote_ip and remote_ip not in known_ips and cfg.is_in_scope(remote_ip):
                    new_ips.append((remote_ip, remote_chassis))
                    known_ips.add(remote_ip)

        if not new_ips:
            break

        logger.info(
            "Recursive LLDP walk (iteration %d): found %d new IPs to probe",
            iteration,
            len(new_ips),
        )
        new_probes = discover_devices(
            new_ips,
            get_credentials=cfg.get_snmp_credentials,
            max_workers=cfg.concurrency,
        )
        for probe in new_probes:
            if probe.is_managed:
                managed.append(probe)
                creds = cfg.get_snmp_credentials(probe.ip)
                collector = GenericSnmpCollector(probe, creds)
                try:
                    device, lldp_entries, fdb_entries = collector.collect()
                    devices.append(device)
                    device_lldp[device.id] = (device, lldp_entries)
                    device_fdb[device.id] = (device, fdb_entries)
                    for iface in device.interfaces:
                        if iface.mac:
                            mac_to_ip.setdefault(iface.mac.upper(), probe.ip)
                except Exception as e:
                    logger.error("Failed to collect %s: %s", probe.ip, e)
            else:
                unmanaged.append(probe)

    # 6. Build topology links
    links = build_links(device_lldp)
    logger.info("Built %d links", len(links))

    # 7. Map endpoints
    trunk_ports: set[tuple[str, str]] = set()
    for device_id, (device, lldp_entries) in device_lldp.items():
        for entry in lldp_entries:
            port_idx = entry.get("local_port_index", "")
            if port_idx:
                trunk_ports.add((device_id, port_idx))

    endpoints = map_endpoints(
        device_fdb,
        trunk_ports,
        arp_entries=seed_result.arp_entries,
    )
    logger.info("Mapped %d endpoints", len(endpoints))

    # 8. Export
    scan_result = ScanResult(
        scan_timestamp=datetime.now(timezone.utc),
        seed_device=cfg.seed_host,
        devices=devices,
        links=links,
        endpoints=endpoints,
    )

    export_scan(scan_result, cfg.output_file, fmt=cfg.output_format)
    logger.info("Scan complete. Output: %s", cfg.output_file)


def main():
    parser = argparse.ArgumentParser(
        description="Network topology scanner — discover devices, collect inventory, map links"
    )
    parser.add_argument(
        "-c",
        "--config",
        default="config.yaml",
        help="Path to config file (default: config.yaml)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging"
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Only show errors"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    elif args.quiet:
        logging.basicConfig(level=logging.ERROR)

    try:
        run_scan(args.config)
    except Exception as e:
        logger.error("Scan failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
