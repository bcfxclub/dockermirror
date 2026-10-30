# -*- coding: utf-8 -*-
# 生成自包含、离线的中文版 .plg
# 结构：
#   bash <<'INSTALL'
#     B64_FILE=/boot/.../df-zh.b64
#     mkdir -p "$(dirname $B64_FILE)"
#     cat > "$B64_FILE" <<'B64EOF'
#     <base64>
#     B64EOF
#     OUT=/boot/.../df-zh.txz
#     python3 - "$B64_FILE" "$OUT" <<'PY'
#     import base64, sys
#     open(sys.argv[2], "wb").write(base64.b64decode(sys.stdin.read().replace("", "") .replace("\n", "")))
#     PY
#     installpkg "$OUT"
#     ...
#   INSTALL
import base64, io, os, hashlib

TXZ   = "D:/AI/Work/2026-10-29-21-34-19/dockermirror/i18n/unraid-docker-folders-modern-2026.10.29-zh1.txz"
OUT   = "D:/AI/Work/2026-10-29-21-34-19/dockermirror/unraid-docker-folders-modern-zh.plg"
NAME  = "unraid-docker-folders-modern"
VER   = "2026.10.29-zh1"

with open(TXZ, "rb") as f:
    txz = f.read()
md5 = hashlib.md5(txz).hexdigest()
b64 = base64.b64encode(txz).decode("ascii")
b64_blob = "\n".join(b64[i:i+76] for i in range(0, len(b64), 76))
assert "]]>" not in b64_blob

install_script = """bash <<'INSTALL'
set -e
B64_FILE="/boot/config/plugins/%s/.pkg-%s.b64"
TXZ_OUT="/boot/config/plugins/%s/%s-ZH.txz"
PLUGIN_NAME="%s"
mkdir -p "$(dirname "$B64_FILE")"

echo "[zh] Decoding embedded offline package..." >&2
cat > "$B64_FILE" <<'B64EOF'
%s
B64EOF

python3 - "$B64_FILE" "$TXZ_OUT" <<'PYDECODE'
import base64, sys
src, dst = sys.argv[1], sys.argv[2]
data = base64.b64decode(open(src, "r").read().replace("\\n",""))
open(dst, "wb").write(data)
print("[zh] decoded to", dst, "size:", len(data), "bytes")
PYDECODE

[ -s "$TXZ_OUT" ] || { echo "[zh] decode produced empty file" >&2; exit 1; }

# 移除旧版本
for old in /var/log/packages/${PLUGIN_NAME}-*; do
  [ -f "$old" ] && removepkg "$(basename "$old")" 2>/dev/null || true
done

installpkg "$TXZ_OUT"

# 离线模式：使用自带 PHP 后端，移除需联网的 GraphQL API 插件目录（若存在）
echo "php" > "/boot/config/plugins/${PLUGIN_NAME}/backend-mode"
[ -d "/boot/config/plugins/${PLUGIN_NAME}/api-plugin" ] && rm -rf "/boot/config/plugins/${PLUGIN_NAME}/api-plugin"

rm -f "$B64_FILE"
echo "[zh] ${PLUGIN_NAME} installed (PHP backend, offline)." >&2
INSTALL""" % (NAME, VER, NAME, VER, NAME, b64_blob)

remove_body = """#!/bin/bash
PLUGIN_NAME="%s"
CONFIG_DIR="/boot/config/plugins/${PLUGIN_NAME}"
PLUGIN_DIR="/usr/local/emhttp/plugins/${PLUGIN_NAME}"
echo "[zh] Removing ${PLUGIN_NAME}..." >&2
for old in /var/log/packages/${PLUGIN_NAME}-*; do
  [ -f "$old" ] && removepkg "$(basename "$old")" 2>/dev/null || true
done
rm -rf "${PLUGIN_DIR}"
rm -f  "${CONFIG_DIR}"/*.txz "${CONFIG_DIR}"/*.b64
echo "[zh] ${PLUGIN_NAME} removed. (config/data kept in ${CONFIG_DIR})" >&2
""" % NAME

plg = []
plg.append('<?xml version="1.0"?>')
plg.append('<PLUGIN name="%s" version="%s" author="Kevin(zh)"' % (NAME, VER))
plg.append('        pluginURL="" pluginWebPage="" launch="Docker/%s" min="7.0.0">' % NAME)
plg.append('<CHANGES>')
plg.append('* %s - 中文本地版：Docker 文件夹（容器分组 / Compose 管理 / 备份计划）离线安装包。' % VER)
plg.append('  内嵌 .txz（base64），无需联网；默认使用自带 PHP 后端，关闭需联网的 GraphQL API 插件。')
plg.append('  数据保存在 /boot/config/plugins/%s/。' % NAME)
plg.append('</CHANGES>')

plg.append('<FILE Run="/bin/bash"><INLINE><![CDATA[')
plg.append(install_script.rstrip())
plg.append(']]></INLINE></FILE>')

plg.append('<REMOVE><INLINE><![CDATA[')
plg.append(remove_body.rstrip())
plg.append(']]></INLINE></REMOVE>')
plg.append('</PLUGIN>')

final = "\n".join(plg) + "\n"
with io.open(OUT, "w", encoding="utf-8") as f:
    f.write(final)

print("written:", OUT)
print("size bytes:", len(final))
print("md5(txz):", md5)

import xml.etree.ElementTree as ET
try:
    ET.fromstring(final)
    print("XML parse: OK")
except ET.ParseError as e:
    print("XML parse FAIL:", e)
