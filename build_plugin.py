#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dockermirror 插件构建脚本

产出：
  1. dist/dockermirror-<VER>.tgz          - 插件本体（GitHub Release 托管）
  2. dist/dockermirror.plg                - GitHub 部署版（从 Release 下载 tgz）
  3. dist/dockermirror-local.plg          - 本地自包含版（tgz 以 base64 内嵌，可离线安装）

用法：
  python3 build_plugin.py
"""
import os
import re
import shutil
import tarfile
import hashlib
import base64
import io

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")
DIST = os.path.join(HERE, "dist")

# 版本号：CI 中由 git tag 注入（环境变量 TAG），本地构建则用默认值
VER = os.environ.get("TAG") or os.environ.get("VERSION") or "2026.10.30"

# ==== GitHub 仓库（已指向你的账号）====
GITHUB_USER = os.environ.get("GITHUB_USER") or "bcfxclub"
GITHUB_REPO = os.environ.get("GITHUB_REPO") or "dockermirror"
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH") or "main"
# =======================================

PLUGIN = "dockermirror"
TGZ_NAME = f"{PLUGIN}-{VER}.tgz"
BUNDLE_URL = (
    f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/releases/download/"
    f"{VER}/{TGZ_NAME}"
)
PLG_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{GITHUB_BRANCH}/{PLUGIN}.plg"
PROJECT_URL = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}"


def ensure_lf(path):
    """确保脚本类文件为 LF 行尾（Unraid 执行 CRLF 脚本会失败）"""
    if not os.path.isfile(path):
        return
    with open(path, "rb") as f:
        data = f.read()
    new = data.replace(b"\r\n", b"\n")
    if new != data:
        with open(path, "wb") as f:
            f.write(new)
        print(f"  [LF] 已转换行尾: {os.path.relpath(path, HERE)}")


def normalize_tree():
    """统一源码行尾"""
    for root, dirs, files in os.walk(SRC):
        for fn in files:
            p = os.path.join(root, fn)
            if fn.endswith((".sh", ".page", ".cfg", ".md")) or not os.path.splitext(fn)[1]:
                ensure_lf(p)

    # 行尾修正后，脚本必须可执行
    for rel in ("scripts/apply.sh", "event/starting", "event/started"):
        p = os.path.join(SRC, "usr/local/emhttp/plugins", PLUGIN, rel)
        if os.path.exists(p):
            os.chmod(p, 0o755)


def build_tgz():
    """把 src/usr/... 打包为 tgz（解压到 / 即可）"""
    os.makedirs(DIST, exist_ok=True)
    tgz_path = os.path.join(DIST, TGZ_NAME)
    if os.path.exists(tgz_path):
        os.remove(tgz_path)

    with tarfile.open(tgz_path, "w:gz") as tar:
        tar.add(os.path.join(SRC, "usr"), arcname="usr")
    md5 = hashlib.md5(open(tgz_path, "rb").read()).hexdigest()
    size = os.path.getsize(tgz_path)
    print(f"  [TGZ] {TGZ_NAME}  ({size} bytes, md5={md5})")
    return tgz_path, md5


def install_script(ver):
    """安装脚本：只做解压与权限，不重启任何服务（避免触发后台提示）"""
    return f"""#!/bin/bash
NAME="{PLUGIN}"
VER="{ver}"
PLUGIN_DIR="/usr/local/emhttp/plugins/${{NAME}}"
CONFIG="/boot/config/plugins/${{NAME}}"
TGZ="${{CONFIG}}/${{NAME}}-${{VER}}.tgz"

mkdir -p "${{PLUGIN_DIR}}" "${{CONFIG}}"
tar -xzf "${{TGZ}}" -C / 2>/dev/null

chmod 755 "${{PLUGIN_DIR}}/scripts"/*.sh 2>/dev/null
chmod 755 "${{PLUGIN_DIR}}/event"/* 2>/dev/null
chmod 644 "${{PLUGIN_DIR}}"/*.page 2>/dev/null
chmod 644 "${{PLUGIN_DIR}}"/*.png 2>/dev/null

# 首次安装生成默认配置（已存在则保留用户设置）
if [ ! -f "${{CONFIG}}/${{NAME}}.cfg" ]; then
  cp "${{PLUGIN_DIR}}/default.cfg" "${{CONFIG}}/${{NAME}}.cfg" 2>/dev/null
fi
chmod 644 "${{CONFIG}}/${{NAME}}.cfg" 2>/dev/null

# 只写入配置，不重启 Docker
"${{PLUGIN_DIR}}/scripts/apply.sh" --no-restart >/dev/null 2>&1

echo "[${{NAME}}] 安装完成（未重启 Docker）"
exit 0
"""


def remove_script():
    """卸载脚本：只删除文件，不碰 daemon.json、不重启 Docker"""
    return f"""#!/bin/bash
NAME="{PLUGIN}"
rm -rf "/usr/local/emhttp/plugins/${{NAME}}"
rm -rf "/boot/config/plugins/${{NAME}}"
echo "[${{NAME}}] 已卸载（未重启 Docker）"
exit 0
"""


def plg_github(md5):
    """GitHub 部署版 plg"""
    return f"""<?xml version='1.0' standalone='yes'?>
<!DOCTYPE PLUGIN [
<!ENTITY name      "{PLUGIN}">
<!ENTITY author    "Kevin">
<!ENTITY version   "{VER}">
<!ENTITY pluginURL "{PLG_URL}">
<!ENTITY bundle    "{TGZ_NAME}">
<!ENTITY bundleURL "{BUNDLE_URL}">
<!ENTITY md5       "{md5}">
]>
<PLUGIN name="&name;"
        author="&author;"
        version="&version;"
        pluginURL="&pluginURL;"
        launch="Settings/Dockermirror"
        icon="globe"
        min="6.9.0"
        support="{PROJECT_URL}/issues"
        project="{PROJECT_URL}"
        readme="{PROJECT_URL}#readme">

<CHANGES>
### {VER}
- 修复安装/卸载时弹出「操作将在后台继续进行」提示：
  安装与卸载脚本已精简为纯文件操作，不再重启 nginx、不再调用 python3。
- 安装、卸载、开机均不会重启 Docker，绝不中断正在运行的容器。
- 开机钩子改为 event/starting（Docker 启动前写入配置），开机即生效且零重启。
- 修正腾讯云镜像源地址。
- 去除 python3 依赖；daemon.json 改用纯 bash 处理，规避 sed 对 URL 斜杠的转义问题。
- 支持通过 GitHub Release 部署与更新。

### 2026.10.29.26
- 旧版本（base64 内嵌包），存在安装耗时触发后台提示的问题。
</CHANGES>

<DESCRIPTION>
一键切换 Docker 镜像加速源，提升镜像拉取速度；支持预设源与自定义，配置保存至 U 盘、开机自动生效、重启不丢失。
</DESCRIPTION>

<!-- 1. 下载插件包到 U 盘 -->
<FILE Name="/boot/config/plugins/&name;/&bundle;">
<URL>&bundleURL;</URL>
<MD5>&md5;</MD5>
</FILE>

<!-- 2. 解压安装（纯文件操作，立即完成） -->
<FILE Run="/bin/bash">
<INLINE>
<![CDATA[
{install_script(VER)}]]>
</INLINE>
</FILE>

<!-- 3. 卸载（纯删除，立即完成） -->
<FILE Run="/bin/bash" Method="remove">
<INLINE>
<![CDATA[
{remove_script()}]]>
</INLINE>
</FILE>

</PLUGIN>
"""


def plg_local(tgz_path):
    """本地自包含版 plg（tgz 以 base64 内嵌，可离线安装）"""
    with open(tgz_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    # 每 76 字符换行，避免单行过长
    b64_lines = "\n".join(b64[i:i + 76] for i in range(0, len(b64), 76))

    inline = f"""#!/bin/bash
NAME="{PLUGIN}"
VER="{VER}"
CONFIG="/boot/config/plugins/${{NAME}}"
PLUGIN_DIR="/usr/local/emhttp/plugins/${{NAME}}"
B64="${{CONFIG}}/.bundle.b64"
TGZ="${{CONFIG}}/${{NAME}}-${{VER}}.tgz"

mkdir -p "${{CONFIG}}" "${{PLUGIN_DIR}}"
cat > "${{B64}}" <<'B64EOF'
{b64_lines}
B64EOF

base64 -d "${{B64}}" > "${{TGZ}}" 2>/dev/null
rm -f "${{B64}}"
tar -xzf "${{TGZ}}" -C / 2>/dev/null

chmod 755 "${{PLUGIN_DIR}}/scripts"/*.sh 2>/dev/null
chmod 755 "${{PLUGIN_DIR}}/event"/* 2>/dev/null
chmod 644 "${{PLUGIN_DIR}}"/*.page 2>/dev/null
chmod 644 "${{PLUGIN_DIR}}"/*.png 2>/dev/null

if [ ! -f "${{CONFIG}}/${{NAME}}.cfg" ]; then
  echo 'MIRRORS=""' > "${{CONFIG}}/${{NAME}}.cfg"
fi
chmod 644 "${{CONFIG}}/${{NAME}}.cfg" 2>/dev/null

"${{PLUGIN_DIR}}/scripts/apply.sh" --no-restart >/dev/null 2>&1
echo "[${{NAME}}] 安装完成（未重启 Docker）"
exit 0
"""

    return f"""<?xml version='1.0' standalone='yes'?>
<!DOCTYPE PLUGIN [
<!ENTITY name    "{PLUGIN}">
<!ENTITY author  "Kevin">
<!ENTITY version "{VER}">
]>
<PLUGIN name="&name;"
        author="&author;"
        version="&version;"
        pluginURL=""
        launch="Settings/Dockermirror"
        icon="globe"
        min="6.9.0">

<CHANGES>
### {VER}
- 本地自包含版：插件文件内嵌，无需外网即可安装。
- 安装/卸载不重启任何服务，不会出现「操作将在后台继续进行」提示。
- 安装、卸载、开机均不重启 Docker。
</CHANGES>

<DESCRIPTION>
一键切换 Docker 镜像加速源（本地离线安装版）。配置保存至 U 盘，开机自动生效、重启不丢失。
</DESCRIPTION>

<FILE Run="/bin/bash">
<INLINE>
<![CDATA[
{inline}]]>
</INLINE>
</FILE>

<FILE Run="/bin/bash" Method="remove">
<INLINE>
<![CDATA[
{remove_script()}]]>
</INLINE>
</FILE>

</PLUGIN>
"""


def main():
    print("== 1. 规范化源码行尾 ==")
    normalize_tree()

    print("== 2. 打包 tgz ==")
    tgz_path, md5 = build_tgz()

    print("== 3. 生成 plg ==")
    github_plg = os.path.join(DIST, f"{PLUGIN}.plg")
    with open(github_plg, "w", encoding="utf-8", newline="\n") as f:
        f.write(plg_github(md5))
    print(f"  [PLG] {PLUGIN}.plg  (GitHub 部署版)")

    local_plg = os.path.join(DIST, f"{PLUGIN}-local.plg")
    with open(local_plg, "w", encoding="utf-8", newline="\n") as f:
        f.write(plg_local(tgz_path))
    print(f"  [PLG] {PLUGIN}-local.plg  (本地离线版)")

    # 复制一份 plg 到仓库根目录，方便 raw 引用
    root_plg = os.path.join(HERE, f"{PLUGIN}.plg")
    shutil.copy(github_plg, root_plg)
    print(f"  [PLG] 仓库根目录 {PLUGIN}.plg 已同步")

    print("\n完成。产物位于 dist/：")
    print(f"  - {TGZ_NAME}          （上传 GitHub Release）")
    print(f"  - {PLUGIN}.plg         （GitHub 部署用，raw 地址安装）")
    print(f"  - {PLUGIN}-local.plg   （本地离线安装用）")
    print(f"\nGitHub Release 地址需为：{BUNDLE_URL}")


if __name__ == "__main__":
    main()
