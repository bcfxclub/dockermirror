

#!/bin/bash
# Uninstall: clear registry-mirrors, remove files
NAME="dockermirror"
DAEMON="/etc/docker/daemon.json"
if [ -f "${DAEMON}" ] && command -v python3 >/dev/null 2>&1; then
python3 - "${DAEMON}" <<'PY'
import sys, json, os
p = sys.argv[1]
try:
    d = json.load(open(p)) if os.path.getsize(p) > 0 else {}
except Exception:
    d = {}
d.pop('registry-mirrors', None)
json.dump(d, open(p, 'w'), indent=2)
PY
fi
if docker info >/dev/null 2>&1; then /etc/rc.d/rc.docker restart >/dev/null 2>&1; fi
rm -rf "/usr/local/emhttp/plugins/${NAME}"
rm -rf "/boot/config/plugins/${NAME}"
/etc/rc.d/rc.nginx restart >/dev/null 2>&1
echo "[dockermirror] removed."

