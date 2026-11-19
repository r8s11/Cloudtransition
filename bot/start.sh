#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

for command_name in opencode tailscale python3; do
  command -v "$command_name" >/dev/null 2>&1 || {
    printf 'Missing required command: %s\n' "$command_name" >&2
    exit 1
  }
done

https_port="${BRAIN_HTTPS_PORT:-8443}"
if [[ ! "$https_port" =~ ^[0-9]+$ ]] || (( https_port < 1 || https_port > 65535 )); then
  printf 'BRAIN_HTTPS_PORT must be a port from 1 to 65535.\n' >&2
  exit 1
fi

configured_host="$(opencode service get | python3 -c 'import json, sys; print(json.load(sys.stdin).get("hostname", ""))')"
case "$configured_host" in
  "" | 127.0.0.1 | localhost) ;;
  *)
    printf 'Restricting OpenCode to loopback; Tailscale provides private phone access.\n'
    opencode service set hostname 127.0.0.1 >/dev/null
    ;;
esac

opencode service start >/dev/null
service_url="$(opencode service status)"
case "$service_url" in
  http://127.0.0.1:* | http://localhost:*) ;;
  *)
    printf 'Expected a loopback OpenCode service; got: %s\n' "$service_url" >&2
    exit 1
    ;;
esac

dns_name="$(tailscale status --json | python3 -c 'import json, sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')"
if [[ -z "$dns_name" ]]; then
  printf 'Tailscale did not report a DNS name. Connect Tailscale first.\n' >&2
  exit 1
fi

tailscale serve --bg --yes --https="$https_port" "$service_url"
opencode pair --url "https://${dns_name}:${https_port}"
