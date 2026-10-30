# -*- coding: utf-8 -*-
"""Generate a self-contained offline Chinese .plg for unraid-docker-folders-modern.

Install flow:
  1) decode embedded base64 -> /boot/config/plugins/<name>/<name>-<ver>.txz
  2) installpkg
  3) run official post-install logic (minus the network-dependent GraphQL bits)
  4) remove: removepkg + cleanup
"""
import base64
import hashlib
import io
import os
import xml.etree.ElementTree as ET

NAME = "unraid-docker-folders-modern"
VER = "2026.10.29-zh1"
BASE = "D:/AI/Work/2026-10-29-21-34-19/dockermirror"
TXZ = BASE + "/i18n/unraid-docker-folders-modern-2026.10.29-zh1.txz"
OUT = BASE + "/unraid-docker-folders-modern-zh.plg"

with open(TXZ, "rb") as fh:
    txz = fh.read()
md5 = hashlib.md5(txz).hexdigest()
b64 = base64.b64encode(txz).decode("ascii")
b64_blob = "\n".join(b64[i:i+76] for i in range(0, len(b64), 76))
assert "]]>" not in b64_blob

# ---------------- install body (official logic, offline; no set -e for robustness) ----------------
INSTALL_BODY = r'''#!/bin/bash
# Self-contained offline install (Chinese build)
# Based on official post-install; network-dependent GraphQL bits removed; PHP backend forced.
PLUGIN_NAME="__NAME__"
PLUGIN_DIR="/usr/local/emhttp/plugins/${PLUGIN_NAME}"
CONFIG_DIR="/boot/config/plugins/${PLUGIN_NAME}"
VERSION="__VER__"
TXZ_PATH="${CONFIG_DIR}/${PLUGIN_NAME}-${VERSION}.txz"
LOG_FILE="${CONFIG_DIR}/install.log"

echo "============== Installing ${PLUGIN_NAME} v${VERSION} =============="
mkdir -p "${CONFIG_DIR}/backups" "${CONFIG_DIR}/data"
echo "Installing ${PLUGIN_NAME} v${VERSION}" > "${LOG_FILE}"

# remove old versions (installpkg vs upgradepkg: name-collision workaround)
for old in /var/log/packages/${PLUGIN_NAME}-*; do
  [ -f "$old" ] && removepkg "$(basename "$old")" 2>&1 | grep -v Skipping || true
done

echo "[zh] Installing package: ${TXZ_PATH}"
installpkg "${TXZ_PATH}"

if [ ! -d "${PLUGIN_DIR}" ]; then
  echo "ERROR: Plugin directory not found: ${PLUGIN_DIR}"
  exit 1
fi

# ---- backup existing DB ----
DB_EXISTS=0
if [ -f "${CONFIG_DIR}/data.db" ]; then
  DB_EXISTS=1
  BACKUP_FILE="${CONFIG_DIR}/backups/pre-upgrade-$(date +%Y%m%d)-${VERSION}.db"
  echo "[zh] Backing up existing DB -> ${BACKUP_FILE}"
  php "${PLUGIN_DIR}/scripts/db-copy.php" backup "${CONFIG_DIR}/data.db" "${BACKUP_FILE}" >> "${LOG_FILE}" 2>&1 || \
    echo "WARNING: DB backup failed, continuing" >> "${LOG_FILE}"
fi

# ---- migrations (critical) ----
echo "[zh] Running database migrations..."
if [ ! -f "${PLUGIN_DIR}/scripts/migrate.php" ]; then
  echo "ERROR: Migration script not found"
  exit 1
fi
MIG_OUT=$(php "${PLUGIN_DIR}/scripts/migrate.php" 2>&1)
MIG_RC=$?
echo "$MIG_OUT" >> "${LOG_FILE}"
if [ $MIG_RC -ne 0 ]; then
  echo "ERROR: Database migration failed (rc=$MIG_RC)"
  echo "$MIG_OUT"
  if [ $DB_EXISTS -eq 1 ] && [ -f "${BACKUP_FILE}" ]; then
    php "${PLUGIN_DIR}/scripts/db-copy.php" restore "${BACKUP_FILE}" "${CONFIG_DIR}/data.db" >> "${LOG_FILE}" 2>&1 || true
  fi
  exit 1
fi
echo "[zh] Migration completed."

# ---- permissions ----
echo "[zh] Setting permissions..."
find "${PLUGIN_DIR}" -type d -exec /bin/chmod 755 {} \;
find "${PLUGIN_DIR}" -type f -name "*.page" -exec /bin/chmod 644 {} \;
find "${PLUGIN_DIR}" -type f -name "*.php"  -exec /bin/chmod 644 {} \;
find "${PLUGIN_DIR}" -type f -name "*.sql"  -exec /bin/chmod 644 {} \;
find "${PLUGIN_DIR}" -type f -name "*.sh"   -exec /bin/chmod 755 {} \;
find "${PLUGIN_DIR}" -type f -name "*.html" -exec /bin/chmod 644 {} \;
find "${PLUGIN_DIR}" -type f -name "*.js"   -exec /bin/chmod 644 {} \;
find "${PLUGIN_DIR}" -type f -name "*.css"  -exec /bin/chmod 644 {} \;
[ -d "${PLUGIN_DIR}/event" ] && chmod 755 "${PLUGIN_DIR}/event/"* 2>/dev/null

for s in check-updates.php restore-cron.php compose-autostart.php compose-shutdown.php; do
  [ -f "${PLUGIN_DIR}/scripts/$s" ] && chmod 755 "${PLUGIN_DIR}/scripts/$s" 2>/dev/null
done

# ---- offline: force PHP backend (skip network GraphQL plugin) ----
if [ -f "${PLUGIN_DIR}/scripts/set-backend-mode.php" ]; then
  php "${PLUGIN_DIR}/scripts/set-backend-mode.php" php >> "${LOG_FILE}" 2>&1 || true
fi
if [ -d "${CONFIG_DIR}/api-plugin" ]; then rm -rf "${CONFIG_DIR}/api-plugin"; fi
echo "php" > "${CONFIG_DIR}/backend-mode" 2>/dev/null || true
if [ -d "/usr/local/unraid-api/node_modules/unraid-api-plugin-docker-folders" ] && [ -f "${PLUGIN_DIR}/scripts/api-plugin.sh" ]; then
  chmod 755 "${PLUGIN_DIR}/scripts/api-plugin.sh" 2>/dev/null
  /bin/bash "${PLUGIN_DIR}/scripts/api-plugin.sh" remove >> "${LOG_FILE}" 2>&1 || true
fi
echo "[zh] Backend mode: php (offline)"

# ---- restore cron / user scripts ----
if [ -f "${PLUGIN_DIR}/scripts/restore-cron.php" ]; then
  php "${PLUGIN_DIR}/scripts/restore-cron.php" >> "${LOG_FILE}" 2>&1 || true
fi
[ -f "/etc/cron.d/${PLUGIN_NAME}" ] && rm -f "/etc/cron.d/${PLUGIN_NAME}"
[ -f "${CONFIG_DIR}/data.db" ] && chmod 644 "${CONFIG_DIR}/data.db"

# ---- verify ----
echo "[zh] Verifying installation..."
FAIL=0
for f in DockerFolders.page Folders.page assets/index.html api/folders.php; do
  if [ -a "${PLUGIN_DIR}/$f" ]; then echo "  + $f"; else echo "  - $f MISSING"; FAIL=1; fi
done
[ -f "${CONFIG_DIR}/data.db" ] && echo "  + data.db" || { echo "  - data.db MISSING"; FAIL=1; }

# rescan menus
if [ -x /etc/rc.d/rc.nginx ]; then /etc/rc.d/rc.nginx restart >/dev/null 2>&1; fi

echo ""
echo "============== Install complete ==============="
echo "Access: Docker > Folders  /  Settings > Utilities > Docker Folders"
echo "Log: ${LOG_FILE}"
'''

INSTALL_BODY = INSTALL_BODY.replace("__NAME__", NAME)
INSTALL_BODY = INSTALL_BODY.replace("__VER__", VER)

# ---------------- remove ----------------
REMOVE_BODY = r'''#!/bin/bash
# Uninstall: remove package and clean up (config/data kept)
PLUGIN_NAME="__NAME__"
PLUGIN_DIR="/usr/local/emhttp/plugins/${PLUGIN_NAME}"
CONFIG_DIR="/boot/config/plugins/${PLUGIN_NAME}"
VERSION="__VER__"

echo "[zh] Removing ${PLUGIN_NAME}..."

# backup DB before removal (best-effort)
if [ -f "${CONFIG_DIR}/data.db" ]; then
  mkdir -p "${CONFIG_DIR}/backups"
  php "${PLUGIN_DIR}/scripts/db-copy.php" backup "${CONFIG_DIR}/data.db" "${CONFIG_DIR}/backups/uninstall-$(date +%Y%m%d)-${VERSION}.db" >/dev/null 2>&1 || \
  cp "${CONFIG_DIR}/data.db" "${CONFIG_DIR}/backups/" 2>/dev/null
fi

for old in /var/log/packages/${PLUGIN_NAME}-*; do
  [ -f "$old" ] && removepkg "$(basename "$old")" 2>&1 | grep -v Skipping || true
done

rm -rf "${PLUGIN_DIR}" "${CONFIG_DIR}/api-plugin" "${CONFIG_DIR}"/*.cron
rm -f "${CONFIG_DIR}"/*.txz "${CONFIG_DIR}"/*.b64
rm -f "/etc/cron.d/${PLUGIN_NAME}"

if [ -x /usr/local/sbin/update_cron ]; then /usr/local/sbin/update_cron >/dev/null 2>&1 || true; fi
if [ -x /etc/rc.d/rc.nginx ]; then /etc/rc.0d/rc.nginx restart >/dev/null 2>&1; fi
echo "[zh] ${PLUGIN_NAME} removed. Data kept in ${CONFIG_DIR}/backups/"
'''

REMOVE_BODY = REMOVE_BODY.replace("__NAME__", NAME)
REMOVE_BODY = REMOVE_BODY.replace("__VER__", VER)
REMOVE_BODY = REMOVE_BODY.replace("${CONFIG_DIR}/data", "${CONFIG_DIR}/data")
REMOVE_BODY = REMOVE_BODY.replace("${CONFIG_DIR}/backups", "${CONFIG_DIR}/backups")
REMOVE_BODY = REMOVE_BODY.replace("/etc/rc.0d/rc.nginx restart >/dev/null 2>&1; fi", "/etc/rc.d/rc.nginx restart >/dev/null 2>&1; fi")
REMOVE_BODY = REMOVE_BODY.replace("${CONFIG_DIR}/backups/uninstall-$(date +%Y%m%d)-${VERSION}.db", "${CONFIG_DIR}/backups/uninstall-$(date +%Y%m%d)-${VERSION}.db")

# ---------------- assemble: heredoc + base64 ----------------
INSTALL_SCRIPT = (
    "bash <<'DFINSTALL'\n"
    "PLUGIN_NAME=\"%s\"\n"
    "CONFIG_DIR=\"/boot/config/plugins/${PLUGIN_NAME}\"\n"
    "VERSION=\"%s\"\n"
    "mkdir -p \"${CONFIG_DIR}\"\n"
    "TXZ_PATH=\"${CONFIG_DIR}/${PLUGIN_NAME}-${VERSION}.txz\"\n"
    "\n"
    "echo \"[zh] Decoding embedded offline package...\"\n"
    "cat > \"${CONFIG_DIR}/.pkg.b64\" <<'B64EOF'\n"
    "%s\n"
    "B64EOF\n"
    "\n"
    "python3 - \"${CONFIG_DIR}/.pkg.b64\" \"${TXZ_PATH}\" <<'PYDEC'\n"
    "import base64, sys\n"
    "src, dst = sys.argv[1], sys.argv[2]\n"
    "data = open(src).read().replace('\\\\n', '')\n"
    "open(dst, 'wb').write(base64.b64decode(data))\n"
    "PYDEC\n"
    "rm -f \"${CONFIG_DIR}/.pkg.b64\"\n"
    "[ -s \"${TXZ_PATH}\" ] || { echo '[zh] decode failed'; exit 1; }\n"
    "\n"
    "%s\n"
    "DFINSTALL\n"
) % (NAME, VER, b64_blob, INSTALL_BODY)

# ---------------- write .plg ----------------
plg = []
plg.append('<?xml version="1.0"?>')
plg.append('<PLUGIN name="%s" version="%s" author="Kevin(zh)"' % (NAME, VER))
plg.append('        pluginURL="" pluginWebPage="" launch="Docker/Folders" min="7.0.0">')
plg.append('<CHANGES>')
plg.append('* %s - Docker Folders Chinese local offline build' % VER)
plg.append('  - Full Chinese UI: Vue3 frontend + .page menu titles')
plg.append('  - Self-contained: .txz embedded as base64, zero network during install')
plg.append('  - Offline backend: built-in PHP backend (GraphQL plugin needs network, disabled)')
plg.append('  - Official install logic kept: migrations, permissions, cron restore, event hooks, verify')
plg.append('</CHANGES>')
plg.append('')
plg.append('<!-- Self-contained offline install: decode embedded base64 -> installpkg -> post-install -->')
plg.append('<FILE Run="/bin/bash"><INLINE><![CDATA[')
plg.append(INSTALL_SCRIPT.rstrip())
plg.append(']]></INLINE></FILE>')
plg.append('')
plg.append('<REMOVE><INLINE><![CDATA[')
plg.append(REMOVE_BODY.rstrip())
plg.append(']]></INLINE></REMOVE>')
plg.append('</PLUGIN>')

final = "\n".join(plg) + "\n"
with io.open(OUT, "w", encoding="utf-8") as fh:
    fh.write(final)

print("written:", OUT)
print("size bytes:", len(final))
print("md5(txz): ", md5)

try:
    ET.fromstring(final)
    print("XML parse: OK")
except ET.ParseError as e:
    print("XML parse FAIL:", e)
