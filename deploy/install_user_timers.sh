#!/usr/bin/env bash
# Install the ingestion timers as systemd *user* units (no root needed).
# Usage: deploy/install_user_timers.sh [--enable]
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
dest="$HOME/.config/systemd/user"
mkdir -p "$dest"
cp "$here"/mpe-ingest-*.service "$here"/mpe-ingest-*.timer "$dest"/
systemctl --user daemon-reload
if [[ "${1:-}" == "--enable" ]]; then
  systemctl --user enable --now mpe-ingest-polymarket.timer mpe-ingest-stocks.timer
  echo "Enabled. Run 'loginctl enable-linger $USER' once so timers keep running while logged out."
fi
systemctl --user list-timers 'mpe-*' --all || true
