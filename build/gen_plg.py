# -*- coding: utf-8 -*-
"""Pack build/dockermirror into a bundle tgz and emit a standard Unraid .plg.

Install pattern mirrors the proven libvirt.hotplug.usb plugin:
  decode embedded bundle -> tar -xzf into /usr/local/emhttp/plugins -> chmod
All steps use the standard <FILE Run="/bin/bash"> element.
"""
import base64
import hashlib
import os
import stat
import tarfile
import xml.etree.ElementTree as ET

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, "build", "dockermirror")
NAME = "dockermirror"
VERSION = "2026.10.29.26"
OUT_TGZ = os.path.join(BASE, "build", "%s-%s.tgz" % (NAME, VERSION))
OUT_PLG = os.path.join(BASE, "dockermirror.plg")

# ----------------------------------------------------------------- bundle ----
# decide mode per file so permissions survive untar on Unraid
def mode_for(arc):
    if arc.endswith("/"):
        return 0o755
    low = arc.lower()
    if low.endswith(".sh") or "/event/" in arc or "/scripts/" in arc:
        return 0o755
    return 0o644


if os.path.exists(OUT_TGZ):
    os.remove(OUT_TGZ)

with tarfile.open(OUT_TGZ, "w:gz") as tar:
    for root, dirs, files in os.walk(SRC):
        rel_root = os.path.relpath(root, os.path.dirname(SRC))       # dockermirror/...
        rel_root = rel_root.replace("\\", "/")
        ti = tar.gettarinfo(root, arcname=rel_root + "/")
        ti.mode = 0o755
        ti.uid = ti.gid = 0
        ti.uname = ti.gname = "root"
        tar.addfile(ti)
        for name in sorted(files):
            full = os.path.join(root, name)
            arc = (rel_root + "/" + name).replace("\\", "/")
            tf = tar.gettarinfo(full, arcname=arc)
            tf.mode = mode_for(arc)
            tf.uid = tf.gid = 0
            tf.uname = tf.gname = "root"
            with open(full, "rb") as fh:
                tar.addfile(tf, fh)

tgz_bytes = open(OUT_TGZ, "rb").read()
md5 = hashlib.md5(tgz_bytes).hexdigest()
b64 = base64.b64encode(tgz_bytes).decode("ascii")
b64_blob = "\n".join(b64[i:i + 76] for i in range(0, len(b64), 76))
assert "]]>" not in b64_blob

# ----------------------------------------------------------- install steps ----
STEP_DECODE = r'''#!/bin/bash
# Step 1: decode the embedded bundle to the flash drive
NAME="%s"
VER="%s"
CONFIG="/boot/config/plugins/${NAME}"
TGZ="${CONFIG}/${NAME}-${VER}.tgz"
B64="${CONFIG}/.bundle.b64"

mkdir -p "${CONFIG}"
cat > "${B64}" <<'B64EOF'
%s
B64EOF

rm -f "${TGZ}"
if command -v base64 >/dev/null 2>&1; then
  base64 -d "${B64}" > "${TGZ}" 2>/dev/null
fi
if [ ! -s "${TGZ}" ] && command -v python3 >/dev/null 2>&1; then
python3 - "${B64}" "${TGZ}" <<'PY'
import base64, sys
src, dst = sys.argv[1], sys.argv[2]
open(dst, 'wb').write(base64.b64decode(open(src).read().replace('\n', '')))
PY
fi
rm -f "${B64}"

if [ ! -s "${TGZ}" ]; then
  echo "[dockermirror] ERROR: bundle decode failed"
  exit 1
fi
echo "[dockermirror] bundle ready: ${TGZ} (md5 %s)"
''' % (NAME, VERSION, b64_blob, md5)

STEP_EXTRACT = r'''#!/bin/bash
# Step 2: extract into the webGui tree and fix permissions
NAME="dockermirror"
VER="%s"
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
''' % VERSION

STEP_VERIFY = r'''#!/bin/bash
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
'''

STEP_REMOVE = r'''#!/bin/bash
# Uninstall: clear registry-mirrors (no Docker restart), remove files
NAME="dockermirror"
DAEMON="/etc/docker/daemon.json"
# 仅从配置文件移除 registry-mirrors 键；不重启 Docker，避免无谓的容器全量重启
# （运行中的 Docker 会在下次重启时自然生效，卸载不应干扰正在运行的容器）
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
rm -rf "/usr/local/emhttp/plugins/${NAME}"
rm -rf "/boot/config/plugins/${NAME}"
/etc/rc.d/rc.nginx restart >/dev/null 2>&1
echo "[dockermirror] removed (Docker 未被重启)."
'''

CHANGES = [
    "* 2026.10.29.26 - 彻底修复「保存后空白页」问题",
    "  - 根因：#command 和 #file 不应放在 .page 头部，而应作为表单隐藏字段",
    "  - 修复：移除头部 #command，改为输入框隐藏字段 name=command",
    "  - 新增输入框隐藏字段 name=file 指向配置文件路径",
    "  - 表单添加 target=progressFrame 实现后台提交不白屏",
    "  - 改用 Unraid 标准按钮 #default / #apply（自动启停）",
    "  - 新增 default.cfg 文件供 parse_plugin_cfg() 使用",
    "* 2026.10.29.25 - 改用 Unraid 标准插件设置页格式",
    "  - 添加 #command scripts/apply.sh 指令，保存后自动执行",
    "  - 表单提交到 /update.php（Unraid 内置配置保存端点）",
    "  - 包含 csrf_token 防止 CSRF 攻击",
    "  - 这是 Unraid 官方推荐的插件设置页模式",
    "* 2026.10.29.24 - 移除表单改用直接链接，解决请求被拦截问题",
    "* 2026.10.29.23 - 重构表单为纯 GET 提交 + 增强调试日志",
    "  - 表单 method=get，隐藏字段 action=apply，避免任何 POST 被拦截的可能",
    "  - PHP 用 $_REQUEST 同时支持 GET/POST",
    "  - 新增 /tmp/dockermirror-debug.log，记录每次请求的 METHOD、GET、POST 内容",
    "  - 写入 cfg 文件后记录成功/失败状态",
    "* 2026.10.29.22 - 改用 GET 方法提交，避免 POST 被 Unraid 框架拦截",
    "  - 问题：POST 表单提交也被拦截，配置未写入",
    "  - 修复：表单改 method=get，使用 URL 参数传递；PHP 用 $_REQUEST 接收",
    "  - 新增 /tmp/dockermirror-debug.log 调试日志，记录每次请求",
    "* 2026.10.29.21 - 改用标准表单提交 + nohup 后台执行，解决 AJAX 被拦截问题",
    "  - 根因：Unraid 的 emhttp 可能拦截 AJAX 请求（CSRF 保护），导致 fetch 失败",
    "  - 修复：按钮改回 type=submit，表单正常 POST；PHP 同步保存配置后立即执行 nohup",
    "  - 页面显示'正在应用...'提示，3秒后自动刷新显示最新状态",
    "* 2026.10.29.20 - 重写 apply.sh：移除 python3 依赖，改用纯 bash 实现",
    "  - 问题：Unraid 7.32 未安装 python3，导致 apply.sh 执行失败、配置不生效",
    "  - 修复：完全重写 apply.sh，使用 sed/grep 等 bash 工具操作 daemon.json",
    "  - 保留原有安全逻辑：解析失败不覆盖、仅必要时重启 Docker",
    "* 2026.10.29.19 - 修复「配置未保存」问题：分两步执行（先保存配置→再异步应用）",
    "  - 问题：上版 fetch 可能因 CSRF 或未序列化表单导致配置未写入",
    "  - 修复：第一步同步 POST 保存配置（确保写入），第二步异步调用 apply.sh",
    "  - 新增 /tmp/dockermirror-debug.log 调试日志，方便排查问题",
    "  - 返回 JSON 格式结果，前端显示详细输出",
    "* 2026.10.29.18 - 彻底解决「应用后白屏」：改用 AJAX 异步执行 + 3秒自动刷新",
    "  - 上版 nohup 在 Unraid PHP 环境不可靠，仍会白屏",
    "  - 新版：点「应用配置」时用 fetch() 异步请求，不阻塞页面；3秒后自动刷新显示最新状态",
    "  - 用户点击后立即看到「正在应用配置...」提示，不会白屏",
    "* 2026.10.29.17 - 修复「点击应用后白屏无反应」：改为后台执行 apply.sh + 30秒自动刷新页面",
    "  - 根因：apply.sh 重启 Docker 会掐断 Unraid Web 后端（跑在 Docker 容器内），导致页面响应丢失",
    "  - 修复：点「应用」后改为 nohup 后台执行，不阻塞等待；添加 30 秒倒计时自动刷新 JS",
    "  - 用户操作后即使页面瞬断，30 秒后会自动恢复显示最新状态",
    "* 2026.10.29.16 - 统一插件名：.page 的 Title 由「Docker 镜像源」改为「Docker 镜像源切换」，与插件页(README)名称一致",
    "* 2026.10.29.15 - README 首行改为 Markdown 加粗 **标题**（正常字号），去掉括号内英文 Dockermirror",
    "* 2026.10.29.14 - README 去掉 Markdown 一级标题，避免列表页说明被渲染成超大字号",
    "  - 之前 README 首行用了 # 标题，Unraid 将其渲染为大号加粗字，与其它插件排版不一致",
    "  - 改为纯文本首行 + 空行 + 说明段落，与其它插件说明字号一致",
    "* 2026.10.29.13 - 修正「插件」主列表页说明：改用插件目录 README.md（.plg 的 DESCRIPTION 字段该页不读取）",
    "  - Unraid 的 Plugins 页说明来自插件目录下的 README.md 文件，而非 .plg 里的 DESCRIPTION 字段",
    "  - 新增 build/dockermirror/README.md（中文简介），随 tgz 自动解压到插件目录，列表页即显示说明",
    "* 2026.10.29.12 - 在「插件」主列表页显示说明（.plg 新增 DESCRIPTION 字段，中英双语）",
    "  - 之前仅在 .page 头部加了 Description（用户程序图标下说明），.plg 本体缺 DESCRIPTION",
    "  - 导致「插件」页面里 dockermirror 条目没有说明文字；现已补齐，与其它插件一致",
    "* 2026.10.29.11 - 「用户程序」图标下显示说明 + 插件页顶部补简介",
    "  - .page 头部新增 Description 字段（图标下方一行说明）",
    "  - 插件页面顶部新增一句话简介，说明用途与持久化行为",
    "* 2026.10.29.10 - 菜单形态调整回「用户程序(Utilities)图标」",
    "  - 改回 Menu=\"Utilities\"：插件只作为「用户程序」区域的图标出现，点图标进入 /Settings/Dockermirror",
    "  - 不再以直接菜单项形式出现在设置主菜单里（之前 Menu=\"Settings\" 的副作用）",
    "  - 若升级后仍见旧的「设置菜单项」，请干净重装一次以清除旧版菜单缓存",
    "* 2026.10.29.9 - 彻底杜绝偷偷重启 Docker（用户核心诉求）",
    "  - 卸载步骤不再无条件 rc.docker restart（之前每次 remove+install 都会触发一次全量重启）",
    "  - apply.sh 改为：仅当「运行中的 Docker」实际镜像源与配置不一致时才重启；",
    "    配置未变 / 已匹配 / Docker 未运行 -> 一律不重启（零干扰）",
    "  - 安装、卸载、开机钩子均不会主动重启 Docker，只有页面里点「应用」才会",
    "* 2026.10.29.8 - 安全修复（重要）：apply.sh 不再无谓重启 Docker",
    "  - 仅在 registry-mirrors 真正变化时才重启；默认/未配置镜像源时开机钩子不再触发 Docker 全量重启",
    "  - daemon.json 解析失败不再重置为 {}，保留原文件避免清掉 Unraid 的 Docker 网络配置",
    "  - 菜单改 Menu=\"Settings\"，直接进入设置主侧栏，避免藏在 User Utilities 底部被忽略",
    "* 2026.10.29.7 - 修复页面白屏根因：Dockermirror.page / apply.sh / event/started 误用 CRLF 行尾，",
    "  - Unraid emhttp 无法识别 --- 分隔符导致整页当头部解析、内容空白；已统一转 LF",
    "  - 页面图标改用 FontAwesome(Icon=\"globe\")，去除对 PNG 文件的依赖（之前图标不显示）",
    "* 2026.10.29.6 - 修正安装后快捷入口 launch 路由：Utilities/Dockermirror -> Settings/Dockermirror",
    "  - 与 Unraid 其它插件一致走 /Settings/(PageName) 真实路由（Utilities 是 Settings 的子分组）",
    "* 2026.10.29.5 - 改为标准 .plg 结构（使用 FILE Run 元素搭配 INLINE CDATA，",
    "  - 插件文件改为打包 bundle(tgz) 后解压安装，保证内容与权限正确落盘",
    "  - 修复页面白屏：radio 元素 onchange 属性引号未闭合，吞掉后续内容",
    "  - 移除 .page 内多余的 DOCTYPE/html/head/body（.page 是嵌入渲染的）",
    "  - 新增 Dockermirror.png 图标，并在 .page 头部声明 Icon",
    "  - .page 顶部开启 PHP 错误显示，便于排错",
]

# ------------------------------------------------------------------- plg -----
parts = []
parts.append('<?xml version="1.0"?>')
parts.append('<PLUGIN name="%s" author="Kevin" version="%s"' % (NAME, VERSION))
parts.append('        pluginURL="" launch="Settings/Dockermirror"')
parts.append('        icon="Dockermirror.png" min="6.9.0">')
parts.append('<CHANGES>')
for line in CHANGES:
    parts.append(line)
parts.append('</CHANGES>')
parts.append('')
parts.append('<DESCRIPTION>')
parts.append('Switch Docker registry mirrors (镜像源) to speed up image pulls. '
             'Set a preset or custom mirror, apply with one click, and keep it across reboots.')
parts.append('')
parts.append('一键切换 Docker 镜像加速源，提升镜像拉取速度；支持预设源与自定义，'
             '配置保存至 U 盘、开机自动生效、重启不丢失。')
parts.append('</DESCRIPTION>')
parts.append('')

scripts = [
    ("Decode the embedded bundle to the flash drive", STEP_DECODE),
    ("Unpack into the webGui tree", STEP_EXTRACT),
    ("Verify install and refresh the webGui menu", STEP_VERIFY),
]
for comment, body in scripts:
    parts.append("<!-- %s -->" % comment)
    parts.append('<FILE Run="/bin/bash">')
    parts.append('<INLINE>')
    parts.append('<![CDATA[')
    parts.append(body.rstrip())
    parts.append(']]>')
    parts.append('</INLINE>')
    parts.append('</FILE>')
    parts.append('')

parts.append('<!-- Uninstall -->')
parts.append('<FILE Run="/bin/bash" Method="remove">')
parts.append('<INLINE>')
parts.append('<![CDATA[')
parts.append(STEP_REMOVE.rstrip())
parts.append(']]>')
parts.append('</INLINE>')
parts.append('</FILE>')
parts.append('')
parts.append('</PLUGIN>')

final = "\n".join(parts) + "\n"
open(OUT_PLG, "w", encoding="utf-8").write(final)

print("bundle tgz:", OUT_TGZ, os.path.getsize(OUT_TGZ), "bytes, md5", md5)
print("plg       :", OUT_PLG, os.path.getsize(OUT_PLG), "bytes")

# --------------------------------------------------------------- validate ----
root = ET.fromstring(final)
files = root.findall("FILE")
print("XML OK, root =", root.tag)
print("version  =", root.get("version"))
print("launch   =", root.get("launch"))
print("FILE count =", len(files))
for f in files:
    body = f.findtext("INLINE") or ""
    print("   Run=%s Method=%s len=%d" % (f.get("Run"), f.get("Method"), len(body)))

# every CDATA must round-trip and contain no premature terminator
for f in files:
    body = f.findtext("INLINE") or ""
    if "]]>" in body or "<![CDATA[" in body:
        raise SystemExit("bad CDATA payload")
print("CDATA payloads clean: True")
