from __future__ import annotations

import json
import logging
from pathlib import Path

import yaml

from net_topology.models import ScanResult

logger = logging.getLogger(__name__)


def export_scan(result: ScanResult, output_path: str, fmt: str = "json") -> None:
    """Export scan result to JSON or YAML file."""
    data = result.to_dict()

    if fmt == "json":
        content = json.dumps(data, indent=2, ensure_ascii=False)
    elif fmt == "yaml":
        content = yaml.dump(data, default_flow_style=False, allow_unicode=True)
    else:
        raise ValueError(f"Unsupported output format: '{fmt}'. Use 'json' or 'yaml'.")

    Path(output_path).write_text(content, encoding="utf-8")
    logger.info("Topology exported to %s (%s)", output_path, fmt)
