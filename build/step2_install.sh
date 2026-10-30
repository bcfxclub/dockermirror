

#!/bin/bash
# Step 2: extract into the webGui tree and fix permissions
NAME="dockermirror"
VER="2026.10.29.5"
PLUGIN_DIR="/usr/local/emhttp/plugins/${NAME}"
CONFIG="/boot/config/plugins/${NAME}"
TGZ="${CONFIG}/${NAME}-${VER}.tgz"

rm -rf "${PLUGIN_DIR}"
mkdir -p "${PLUGIN_DIR}"
tar -xzf "${TGZ}" -C /usr/local/emhttp/plugins 2>/dev/null
if [ -f "${PLUGIN_DIR}/${NAME}-${VER}.tgz" ]; then rm -f "${PLUGIN_DIR}/${NAME}-${VER}.tgz"; fi

chown -R root:root "${PLUGIN_DIR}" 2>/dev/null
find "${PLUGIN_DIR}" -type d -exec chmod 755 {} \;
find "${PLUGIN_DIR}" -type f -exec chmod 644 {} \;
chmod 644 "${PLUGIN_DIR}"/*.page 2>/dev/null
chmod 644 "${PLUGIN_DIR}"/*.png 2>/dev/null
find "${PLUGIN_DIR}/scripts" -type f -exec chmod 755 {} \; 2>/dev/null
find "${PLUGIN_DIR}/event"   -type f -exec chmod 755 {} \; 2>/dev/null

if [ ! -f "${CONFIG}/${NAME}.cfg" ]; then
  printf 'MIRRORS=""\n' > "${CONFIG}/${NAME}.cfg"
fi
chmod 644 "${CONFIG}/${NAME}.cfg" 2>/dev/null

