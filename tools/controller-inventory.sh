#!/usr/bin/env bash
# Read-only SourceOS controller inventory collector.
# This script is intentionally non-mutating and does not require sudo.
# It writes a local text report for operator review. Do not commit raw output.

set -u

OUTDIR="${1:-$HOME/Desktop}"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$OUTDIR/controller-inventory-$STAMP.txt"
mkdir -p "$OUTDIR"

section() {
  printf '\n\n### %s\n' "$1"
}

{
  section "time / system"
  date
  sw_vers 2>/dev/null || true
  uname -a 2>/dev/null || true
  uptime 2>/dev/null || true

  section "active controller processes"
  ps axww -o pid,ppid,user,%cpu,%mem,rss,etime,command \
    | egrep 'photolibraryd|photoanalysisd|mediaanalysisd|cloudphotod|cloudd|fileproviderd|mds|mdworker|mds_stores|spotlight|corespotlight|apfsd|airportd|wifip2pd|wifianalyticsd|symptomsd|networkserviceproxy|nesessionmanager|Firefox|updater|softwareupdated|nsurlsessiond|rapportd|sharingd|mDNSResponder|apsd|LuLu|BlockBlock' \
    | egrep -v 'egrep' || true

  section "top cpu processes"
  ps axww -o pid,ppid,user,%cpu,%mem,rss,etime,command | sort -nrk4 | head -40

  section "recent diagnostic report names"
  ls -lt /Library/Logs/DiagnosticReports "$HOME/Library/Logs/DiagnosticReports" 2>/dev/null \
    | egrep 'photolibraryd|photoanalysisd|mediaanalysisd|cloud|mds|spotlight|corespotlight|apfsd|fileproviderd|Firefox|firefox|updater|airportd|networkserviceproxy|shutdown_stall|Jetsam|cpu_resource|diag|ips' \
    | head -160 || true

  section "spotlight indexed volumes"
  mdutil -as 2>&1 || true

  section "system launchd controller services"
  launchctl print system 2>/dev/null \
    | egrep -i 'metadata|mds|spotlight|corespotlight|photo|cloudphoto|photolibrary|mediaanalysis|privatecloud|cloudd|cloudkit|fileprovider|searchparty|airport|wifi|corewifi|wifip2p|wifianalytics|networkserviceproxy|nesession|mDNSResponder|rapport|sharingd|apsd' \
    | head -320 || true

  section "user launchd controller services"
  launchctl print "gui/$(id -u)" 2>/dev/null \
    | egrep -i 'metadata|mds|spotlight|corespotlight|photo|cloudphoto|photolibrary|mediaanalysis|privatecloud|cloudd|cloudkit|fileprovider|searchparty|BluetoothCloud|BTServer.cloud|airport|wifi|corewifi|wifip2p|wifianalytics|networkserviceproxy|nesession|mDNSResponder|rapport|sharingd|apsd' \
    | head -420 || true

  section "interfaces"
  ifconfig -a 2>&1 | egrep '^[a-z0-9]+:|status:|ether |inet |inet6 |media:|nd6 options|flags=' || true

  section "active network paths"
  scutil --nwi 2>&1 || true

  section "routes ipv4"
  netstat -rn -f inet 2>&1 || true

  section "routes ipv6"
  netstat -rn -f inet6 2>&1 | head -220 || true

  section "dns"
  scutil --dns 2>&1 || true

  section "network services"
  networksetup -listallhardwareports 2>&1 || true
  networksetup -listallnetworkservices 2>&1 || true

  section "system extensions"
  systemextensionsctl list 2>&1 || true

  section "network extension connections"
  scutil --nc list 2>&1 || true

} | tee "$OUT"

echo "WROTE $OUT"
