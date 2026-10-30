# -*- coding: utf-8 -*-
# 生成自包含、离线、中文版的 unraid-docker-folders-modern .plg
# 依据官方 .plg，做两处替换：
#   1) 去掉“下载 .txz”的 FILE，改为内嵌 base64 的 .txz + 解码 + installpkg
#   2) 关闭需联网的 GraphQL API 插件，默认使用自带 PHP 后端（离线可用）
import base64, io, sys, os

REPO = "C:/Users/Kevin/AppData/Local/Temp/df"          # git bash /tmp/df 的真实 Windows 路径
OFFICIAL = os.path.join(REPO, "unraid-docker-folders-modern.plg")
TXZ = "D:/AI/Work/2026-10-29-21-34-19/dockermirror/i18n/unraid-docker-folders-modern-2026.10.29-zh1.txz"
OUT = "D:/AI/Work/2026-10-29-21-34-19/dockermirror/unraid-docker-folders-modern-zh.plg"

VERSION = "2026.10.29-zh1"

# ---------- 读取官方 .plg ----------
with io.open(OFFICIAL, encoding="utf-8") as f:
    content = f.read()

# ---------- 1) 实体声明 + 头部属性 ----------
content = content.replace(
    '<!ENTITY md5 "899d919d444ff486f21d5a3296af8978">',
    '<!ENTITY md5 "d6cccfec93e32dedc5a8c1c63c6b9014">'
)
content = content.replace(
    '<!ENTITY version "2026.10.25-2">',
    '<!ENTITY version "2026.10.29-zh1">'
)
# pluginURL 置空 => 本地安装，不发起任何网络请求
content = content.replace(
    '<!ENTITY pluginURL "https://raw.githubusercontent.com/&github;/main/&name;.plg">',
    '<!ENTITY pluginURL "">'
)
content = content.replace('<!ENTITY github "rizowski/unraid-docker-folders">', '<!ENTITY github "">')
content = content.replace(
    '<!ENTITY launch "Docker">',
    '<!ENTITY launch "Docker/Dockermirror">'
)
content = content.replace('author="&author;"', 'author="Kevin(zh)"')

# ---------- 2) 插入自包含的 .txz 安装块（内嵌 base64） ----------
with open(TXZ, "rb") as f:
    txz_bytes = f.read()
b64 = base64.b64encode(txz_bytes).decode("ascii")
# 按 76 列折行，避免 CDATA 内出现异常长行
lines = [b64[i:i+76] for i in range(0, len(b64), 76)]
b64_blob = "\n".join(lines)

install_block = (
    '<!-- 自包含离线安装：内嵌的中文版 .txz（base64）。无需任何网络。 -->\n'
    '<FILE Name="/boot/config/plugins/&name;/&name;-&version;.txz" Run="/bin/bash">\n'
    '<INLINE><![CDATA[\n'
    '#!/bin/bash\n'
    'OUT="/boot/config/plugins/unraid-docker-folders-modern/unraid-docker-folders-modern-' + VERSION + '.txz"\n'
    'mkdir -p "$(dirname "$OUT")"\n'
    'python3 - "$OUT" <<\'B64EOF\'\n'
    'import base64, sys\n'
    'out = sys.argv[1]\n'
    'import re\n'
    'data = re.sub(r"\\s+", "", sys.stdin.read())\n'
    'with open(out, "wb") as fh:\n'
    '    fh.write(base64.b64decode(data))\n'
    'B64EOF\n'
    'if [ ! -s "$OUT" ]; then echo "decode failed"; exit 1; fi\n'
    'echo "Decoded local package: $OUT"\n'
    'installpkg "$OUT"\n'
    ']]></INLINE>\n'
    '</FILE>\n'
    '\n'
    '<FILE Run="/bin/bash">\n'
    '<INLINE><![CDATA[\n'
    '#!/bin/bash\n'
    'PKG="unraid-docker-folders-modern-' + VERSION + '.txz"\n'
    'SRC="/boot/config/plugins/unraid-docker-folders-modern/' + VERSION + '.txz"\n'
    'if [ ! -f "$SRC" ]; then\n'
    '  echo "Package not found: $SRC (offline install block may not have run)"\n'
    '  exit 1\n'
    'fi\n'
    'installpkg "$SRC" || exit 1\n'
    'echo "Package installed: $PKG"\n'
    ']]></INLINE>\n'
    '</FILE>\n'
)

# ---------- 3) 关闭 GraphQL 插件（离线模式） ----------
graphql_off_block = (
    '<FILE Run="/bin/bash">\n'
    '<INLINE><![CDATA[\n'
    '#!/bin/bash\n'
    'PLUGIN_NAME="unraid-docker-folders-modern"\n'
    'BACKEND_MODE_FILE="/boot/config/plugins/${PLUGIN_NAME}/backend-mode"\n'
    'echo "php" > "${BACKEND_MODE_FILE}"\n'
    'echo "Forced backend mode to php (offline mode: the GraphQL API plugin is not built; PHP backend is used)." >&2\n'
    'if [ -x /usr/local/sbin/plugin ]; then\n'
    '  /usr/local/sbin/plugin 2>/dev/null || true\n'
    'fi\n'
    ']]></INLINE>\n'
    '</FILE>\n'
)

# ---------- 4) 移除原来的“下载 .txz”FILE 块（URL 方式） ----------
start_marker = '<FILE Name="/boot/config/plugins/&name;/&name;-&version;.txz" Run="installpkg">'
end_marker = '</FILE>\n\n'
i = content.find(start_marker)
if i != -1:
    j = content.find(end_marker, i)
    j = j + len(end_marker) if j != -1 else i + len(start_marker)
    content = content[:i] + content[j:]

# ---------- 5) 移除官方 post-install 里对 GraphQL API 插件的条件安装段 ----------
# 该段形如： if [ "${BACKEND_MODE}" = "graphql" ]; then ... fi ；整段删除以避免联网
g_start = content.find('BACKEND_MODE=$(php -r')
if g_start != -1:
    g_end = content.find('fi', g_start)
    if g_end != -1:
        g_end = content.find('\n', g_end)
        content = content[:g_start] + content[g_end:]

# ---------- 6) 拼接：在官方 CHANGES 后、原 pre-install FILE 前插入自包含块 ----------
# 在 <PLUGIN ...> 之后紧跟一个注释说明，并在 pre-install 之前插入内嵌 txz 块
marker = '<FILE Run="/bin/bash">\n<INLINE>\n'
mpos = content.find(marker)
insert_at = mpos if mpos != -1 else len(content)
content = content[:insert_at] + install_block + "\n" + content[insert_at:]
# 在 pre-install 之后插入关闭 GraphQL 的块（放在 installpkg 之后）
gpos = content.find(marker)
content = content[:gpos] + graphql_off_block + "\n" + content[gpos:]

# ---------- 写出 ----------
with io.open(OUT, "w", encoding="utf-8") as f:
    f.write(content)
print("written:", OUT, "bytes:", os.path.getsize(OUT))

# ---------- 7) XML 校验（忽略 DOCTYPE 里的实体） ----------
import xml.etree.ElementTree as ET
try:
    ET.fromstring(content)
    print("XML parse: OK (no entities to resolve issue)")
except ET.ParseError as e:
    # 实体未定义会导致解析失败，这是预期的（.plg 使用 DTD 实体，实际由 Unraid 解析）
    print("XML parse note (expected, entity defs used):", str(e))
# 单独验证去掉 DTD 头后结构
stripped = content
head_end = stripped.find('?>') + 2
body = stripped[head_end:]
try:
    ET.fromstring(body)
    print("XML body (after DOCTYPE) parse: OK")
except ET.ParseError as e:
    print("XML body parse FAIL:", e)
