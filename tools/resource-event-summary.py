#!/usr/bin/env python3
"""Summarize local controller resource reports into redacted rows.

Usage:
  python3 tools/resource-event-summary.py <report-file-or-dir> --format markdown

The tool is read-only. It requires explicit input paths and emits summary fields only.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any

SUFFIXES = ('.diag', '.cpu_resource.diag', '.shutdownStall', '.ips')

PATTERNS = {
    'date_time': r'^Date/Time:\s*(.+)$',
    'end_time': r'^End time:\s*(.+)$',
    'command': r'^Command:\s*(.+)$',
    'identifier': r'^Identifier:\s*(.+)$',
    'team_id': r'^Team ID:\s*(.+)$',
    'is_first_party': r'^Is First Party:\s*(.+)$',
    'resource_coalition': r'^Resource Coalition:\s*(.+)$',
    'event': r'^Event:\s*(.+)$',
    'action_taken': r'^Action taken:\s*(.+)$',
    'writes': r'^Writes:\s*(.+)$',
    'cpu': r'^CPU:\s*(.+)$',
    'duration': r'^Duration:\s*(.+)$',
}

CONTROLLERS = [
    (r'mds|mdworker|mds_stores|spotlight|corespotlight', 'Spotlight / Metadata'),
    (r'photolibraryd|photoanalysisd|mediaanalysisd|cloudphotod|Photos', 'Photos / Media'),
    (r'apfsd', 'Filesystem'),
    (r'airportd|wifip2p|wifianalytics|corewifi|WiFi', 'Wireless'),
    (r'networkserviceproxy|nesessionmanager|NetworkExtension|vpn', 'Network Policy'),
    (r'org\.mozilla\.updater|firefox', 'Application Updater'),
    (r'cloudd|fileproviderd|cloudkit|iCloud', 'Cloud / File Provider'),
    (r'ANECompilerService', 'ML / Acceleration'),
]

STACKS = [
    (r'SpotlightIndex|CICompact|index_compact|PayloadPulses|mds', 'index compaction / payload writes'),
    (r'PLCloudPhotoLibraryManager|PLResetSyncStatus|PhotoLibraryServices|NSSQL|sqlite|CoreData', 'media database rewrite'),
    (r'apfsd|fts_read|fts_build|getattrlistbulk|fsctl|fstat|fstatat', 'filesystem traversal'),
    (r'airportdProcessTrafficEngineeringEvents|LQM|WME|CoreWiFi|IO80211', 'wireless telemetry'),
    (r'fwrite|write_nocancel', 'file writes'),
]


def size_mb(text: str) -> float | str:
    match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(KB|MB|GB|TB)', text or '', re.I)
    if not match:
        return ''
    value = float(match.group(1))
    unit = match.group(2).upper()
    scale = {'KB': 1 / 1024, 'MB': 1, 'GB': 1024, 'TB': 1024 * 1024}[unit]
    return round(value * scale, 3)


def cpu_avg(text: str) -> float | str:
    match = re.search(r'\(([0-9]+(?:\.[0-9]+)?)%\s*cpu average\)', text or '', re.I)
    return float(match.group(1)) if match else ''


def classify(text: str, rules: list[tuple[str, str]], default: str) -> str:
    for pattern, label in rules:
        if re.search(pattern, text, re.I):
            return label
    return default


def iter_inputs(paths: list[Path]):
    for path in paths:
        if path.is_file() and path.name.endswith(SUFFIXES):
            yield path
        elif path.is_dir():
            for child in sorted(path.iterdir()):
                if child.is_file() and child.name.endswith(SUFFIXES):
                    yield child


def parse_report(path: Path) -> dict[str, Any]:
    if path.name.endswith('.ips'):
        try:
            obj = json.loads(path.read_text(errors='replace'))
        except Exception:
            obj = {}
        command = str(obj.get('procName', obj.get('bug_type', '')))
        haystack = f'{command} {path.name}'
        return {
            'time': obj.get('timestamp', dt.datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec='seconds')),
            'file': path.name,
            'command': command,
            'controller': classify(haystack, CONTROLLERS, 'Unclassified'),
            'event': 'ips',
            'writes_mb': '',
            'cpu_avg_pct': '',
            'action': '',
            'stack_family': classify(json.dumps(obj)[:5000], STACKS, 'Unclassified'),
        }

    text = path.read_text(errors='replace')
    data = {}
    for key, pattern in PATTERNS.items():
        match = re.search(pattern, text, re.M)
        data[key] = match.group(1).strip() if match else ''
    haystack = f"{data.get('command', '')} {path.name}"
    return {
        'time': data.get('date_time') or dt.datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec='seconds'),
        'file': path.name,
        'command': data.get('command', ''),
        'controller': classify(haystack, CONTROLLERS, 'Unclassified'),
        'event': data.get('event', ''),
        'writes_mb': size_mb(data.get('writes', '')),
        'cpu_avg_pct': cpu_avg(data.get('cpu', '')),
        'action': data.get('action_taken', ''),
        'stack_family': classify(text, STACKS, 'Unclassified'),
    }


def write_markdown(rows: list[dict[str, Any]], out) -> None:
    out.write('# Controller Resource Event Summary\n\n')
    out.write('| Time | Controller | Command | Event | Writes MB | CPU Avg % | Action | Stack family |\n')
    out.write('|---|---|---|---|---:|---:|---|---|\n')
    for row in rows:
        out.write(f"| {row['time']} | {row['controller']} | {row['command']} | {row['event']} | {row['writes_mb']} | {row['cpu_avg_pct']} | {row['action']} | {row['stack_family']} |\n")


def write_csv(rows: list[dict[str, Any]], out) -> None:
    fields = ['time', 'file', 'command', 'controller', 'event', 'writes_mb', 'cpu_avg_pct', 'action', 'stack_family']
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('paths', nargs='+', type=Path)
    parser.add_argument('--format', choices=['markdown', 'csv', 'json'], default='markdown')
    args = parser.parse_args()

    rows = [parse_report(path) for path in iter_inputs(args.paths)]
    if args.format == 'json':
        json.dump(rows, sys.stdout, indent=2)
        sys.stdout.write('\n')
    elif args.format == 'csv':
        write_csv(rows, sys.stdout)
    else:
        write_markdown(rows, sys.stdout)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
