

#!/bin/bash
# Step 3: verify and refresh the menu
NAME="dockermirror"
PLUGIN_DIR="/usr/local/emhttp/plugins/${NAME}"
echo "[dockermirror] verifying installation in ${PLUGIN_DIR}:"
RC=0
for f in Dockermirror.page Dockermirror.png scripts/apply.sh event/started; do
  if [ -f "${PLUGIN_DIR}/$f" ]; then echo "  ok      $f"
  else echo "  MISSING $f"; RC=1; fi
done
echo "[dockermirror] page header:"
head -5 "${PLUGIN_DIR}/Dockermirror.page" 2>/dev/null
/etc/rc.d/rc.nginx restart >/dev/null 2>&1
exit $RC

