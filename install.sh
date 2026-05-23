#!/usr/bin/env bash
#
# Traffic Monitor one-line installer.
#
# Quick install (downloads latest release, installs binary):
#   curl -fsSL https://raw.githubusercontent.com/faker2048/traffic-monitor/master/install.sh | sudo bash
#
# Install AND set up systemd service in one shot (extra args are forwarded to
# `traffic-monitor run ... --install`):
#   curl -fsSL https://raw.githubusercontent.com/faker2048/traffic-monitor/master/install.sh \
#     | sudo bash -s -- --discord https://discord.com/api/webhooks/ID/TOKEN --limit 2048
#
set -euo pipefail

REPO="${TRAFFIC_MONITOR_REPO:-faker2048/traffic-monitor}"
INSTALL_DIR="${TRAFFIC_MONITOR_INSTALL_DIR:-/usr/local/bin}"
BIN_NAME="traffic-monitor"
ASSET_NAME="traffic-monitor-x86_64-linux"
VERSION="${TRAFFIC_MONITOR_VERSION:-latest}"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m  %s\n' "$*" >&2; }
err()  { printf '\033[1;31mxx\033[0m  %s\n' "$*" >&2; }

if [ "$(id -u)" -ne 0 ]; then
    err "This installer must be run as root."
    err "Re-run with: curl ... | sudo bash   (or: sudo bash install.sh)"
    exit 1
fi

ARCH="$(uname -m)"
if [ "$ARCH" != "x86_64" ]; then
    err "Only x86_64 is supported right now (detected: $ARCH)."
    exit 1
fi

OS="$(uname -s)"
if [ "$OS" != "Linux" ]; then
    err "Only Linux is supported (detected: $OS)."
    exit 1
fi

# --- vnstat ----------------------------------------------------------------
if ! command -v vnstat >/dev/null 2>&1; then
    log "Installing vnstat (system dependency)..."
    if command -v apt-get >/dev/null 2>&1; then
        DEBIAN_FRONTEND=noninteractive apt-get update -qq
        DEBIAN_FRONTEND=noninteractive apt-get install -y vnstat
    elif command -v dnf >/dev/null 2>&1; then
        dnf install -y vnstat
    elif command -v yum >/dev/null 2>&1; then
        yum install -y vnstat
    elif command -v pacman >/dev/null 2>&1; then
        pacman -Sy --noconfirm vnstat
    else
        err "No supported package manager found. Please install vnstat manually and re-run."
        exit 1
    fi

    if command -v systemctl >/dev/null 2>&1; then
        systemctl enable --now vnstat >/dev/null 2>&1 || true
    fi
else
    log "vnstat already installed: $(vnstat --version 2>/dev/null | head -1)"
fi

# --- download binary -------------------------------------------------------
if [ "$VERSION" = "latest" ]; then
    DOWNLOAD_URL="https://github.com/${REPO}/releases/latest/download/${ASSET_NAME}"
    CHECKSUM_URL="https://github.com/${REPO}/releases/latest/download/${ASSET_NAME}.sha256"
else
    DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/${ASSET_NAME}"
    CHECKSUM_URL="https://github.com/${REPO}/releases/download/${VERSION}/${ASSET_NAME}.sha256"
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

log "Downloading ${ASSET_NAME} (${VERSION}) from GitHub..."
if ! curl -fL --proto '=https' --tlsv1.2 "$DOWNLOAD_URL" -o "${TMP_DIR}/${BIN_NAME}"; then
    err "Failed to download $DOWNLOAD_URL"
    err "Make sure a release with asset '${ASSET_NAME}' exists at https://github.com/${REPO}/releases"
    exit 1
fi

if curl -fsSL --proto '=https' --tlsv1.2 "$CHECKSUM_URL" -o "${TMP_DIR}/${BIN_NAME}.sha256" 2>/dev/null; then
    log "Verifying checksum..."
    EXPECTED="$(awk '{print $1}' "${TMP_DIR}/${BIN_NAME}.sha256")"
    ACTUAL="$(sha256sum "${TMP_DIR}/${BIN_NAME}" | awk '{print $1}')"
    if [ "$EXPECTED" != "$ACTUAL" ]; then
        err "Checksum mismatch! expected=$EXPECTED actual=$ACTUAL"
        exit 1
    fi
else
    warn "Checksum file not available, skipping verification."
fi

chmod +x "${TMP_DIR}/${BIN_NAME}"
install -m 0755 "${TMP_DIR}/${BIN_NAME}" "${INSTALL_DIR}/${BIN_NAME}"
log "Installed: ${INSTALL_DIR}/${BIN_NAME}"
"${INSTALL_DIR}/${BIN_NAME}" --version || true

# --- optional: install as systemd service ----------------------------------
if [ "$#" -gt 0 ]; then
    log "Setting up systemd service with provided args..."
    "${INSTALL_DIR}/${BIN_NAME}" run "$@" --install
else
    cat <<EOF

Done. Next steps:

  # Run once, just to see current status
  sudo ${BIN_NAME} status

  # Install as systemd service (auto-start on boot) — example:
  sudo ${BIN_NAME} run \\
    --discord https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN \\
    --limit 2048 \\
    --install

Tip: you can also do everything in one go:
  curl -fsSL https://raw.githubusercontent.com/${REPO}/master/install.sh \\
    | sudo bash -s -- --discord <webhook_url> --limit 2048

EOF
fi
