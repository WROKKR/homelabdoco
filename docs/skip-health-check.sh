#!/usr/bin/env bash
# Run manually on ollama2. No credentials or service changes required.
set -u
printf 'Homelab endpoint report\n'
printf 'Collected: %s\n' "$(date -Is)"
printf 'Collector: %s\n' "$(hostname)"
printf 'Scope: HTTP reachability only; no backend, VM, automation or backup validation.\n'

probe() {
  local label="$1" url="$2" result rc tls_note=''
  if [[ "$url" == https:* ]]; then
    # Private Proxmox endpoint may use a self-signed certificate.
    result=$(curl --insecure --silent --output /dev/null --connect-timeout 5 --max-time 15 --write-out 'HTTP=%{http_code} seconds=%{time_total}' "$url" 2>/dev/null)
    rc=$?
    tls_note=' TLS certificate verification skipped'
  else
    result=$(curl --silent --output /dev/null --connect-timeout 5 --max-time 15 --write-out 'HTTP=%{http_code} seconds=%{time_total}' "$url" 2>/dev/null)
    rc=$?
  fi
  printf '%s [%s]: %s curl_exit=%s%s\n' "$label" "$url" "$result" "$rc" "$tls_note"
}

probe Homepage http://192.168.0.160:3001/
probe HomeAssistant http://192.168.0.161:8123/
probe Proxmox https://192.168.0.50:8006/
printf 'HA :8123 and Proxmox :8006 are initial assumed direct endpoints; confirm configuration.\n'
printf 'Interpretation: HTTP response proves a responding endpoint only. 401/403 means access restricted, not necessarily outage; redirects require interpretation. curl failure needs investigation.\n'
