# Docker 镜像源切换插件（dockermirror） for Unraid

## 本目录还包含：Docker Folders 中文本地离线版插件

`unraid-docker-folders-modern-zh.plg`（约 776 KB）
- **完整汉化**：Vue3 前端界面 + `.page` 菜单标题（Docker > Folders / 设置 > Docker 文件夹）
- **自包含离线**：`.txz` 以 base64 内嵌，**安装全程零网络依赖**
- **离线后端**：使用自带 PHP 后端（官方的 GraphQL API 插件需联网下载，已关闭）
- **保留官方安装逻辑**：数据库迁移、权限设置、cron 恢复、事件钩子、安装验证
- 安装：WebGUI → **Plugins → Install Plugin → Local** → 选中该 `.plg` → Install
- 卸载：Plugins → 已安装插件 → 卸载（配置/数据在 `/boot/config/plugins/unraid-docker-folders-modern/`，卸载默认保留）
- 生成脚本：`gen_clean_plg.py`（纯 ASCII，可重复执行）；汉化映射字典：`i18n/translate_map.json`

一个本地可安装的 Unraid 插件，在 WebGUI 的 **Utilities（用户实用工具）** 菜单里提供「Docker 镜像源」设置页，
用于一键切换 Docker 的 registry-mirrors（镜像加速源），支持预设、自定义、恢复默认，并且重启不丢失。

## 功能
- 图形化菜单（Settings → 用户实用工具 → Docker 镜像源）
- 内置多个常用国内镜像源预设（DaoCloud / 腾讯云 / 网易 / 毫秒镜像 / 轩辕 / 百度 / DockerProxy 等）
- 支持自定义任意镜像源地址（可填多个，按顺序尝试）
- 「应用并重启 Docker」与「恢复默认设置」两个按钮
- 配置保存在 U 盘，开机自动重新写入 `/etc/docker/daemon.json`，重启 / 阵列启动均不丢失
- 写入时采用**合并**方式，保留 nvidia runtime 等已有字段，不与 GPU 容器冲突

## 安装（本地安装）
1. 把 `dockermirror.plg` 传到 Unraid 能访问到的地方（例如电脑上）。
2. 打开 Unraid WebGUI → **Plugins（插件）** → **Install Plugin（安装插件）**。
3. 选择 **Local（本地）** 选项卡，点击 **Browse（浏览）** 选中 `dockermirror.plg`，然后 **Install**。
4. 安装完成后，到 **Settings → 用户实用工具（User Utilities）→ Docker 镜像源** 即可使用。

> 也可通过 `Tools` 终端执行：`plugin install /路径/dockermirror.plg`

## 使用
1. 进入 **Settings → 用户实用工具（User Utilities）→ Docker 镜像源**（在 Settings 页底部）。
2. 在「选择镜像源」中点选一个预设，或勾选「自定义」并填入地址（每行一个）。
3. 点击 **应用并重启 Docker**。页面会显示执行结果，并可在「当前状态」中查看生效的镜像源。
4. 想恢复官方直连：点击 **恢复默认设置**。

验证是否生效（终端执行）：
```bash
docker info | grep -A5 "Registry Mirrors"
```

## 卸载
**Plugins → 已安装插件** 中找到 dockermirror，点击卸载即可。卸载脚本会自动清除 daemon.json 中的镜像源并删除配置。

## 排错：安装时报 “xxx is not a plg file”
这是 Unraid 安装器的已知 bug：**文件路径或文件名包含空格时，安装器会按空格切分路径，把第一段当成文件名**，于是出现类似 `plugin: docker is not a plg file` 的报错（说明路径里 “docker” 后面跟了空格）。

解决要点：
1. **文件名不要有空格、不要有中文**，建议就用 `dockermirror.plg`。
2. **文件所在目录也不要有空格**（例如不要放在 “Unraid Docker” 这类文件夹里）。
3. **最稳妥：用终端安装**，绕开 WebUI 的文件选择 bug：
   ```bash
   # 先把 dockermirror.plg 传到服务器，例如放到 /tmp 或 /boot/config/plugins/
   plugin install /tmp/dockermirror.plg
   ```
   或放在 U 盘配置目录时：
   ```bash
   plugin install /boot/config/plugins/dockermirror.plg
   ```
4. 如果坚持用 WebUI 的 **Install Plugin → Local** 选项卡，请确保浏览选中的文件名和所在路径都不含空格。
5. 确认文件扩展名确实是 `.plg`：
   ```bash
   ls -la /tmp/dockermirror.plg
   ```
   若显示成 `.txt` 或没有扩展名，先重命名再加 `.plg`。

> 验证安装结果：`ls /usr/local/emhttp/plugins/dockermirror/` 应能看到 `Dockermirror.page`、`scripts/`、`event/`。

## 技术说明
- 插件目录：`/usr/local/emhttp/plugins/dockermirror/`（内存中，开机由 U 盘重装）
- 持久化配置：`/boot/config/plugins/dockermirror/dockermirror.cfg`（U 盘，重启保留）
- 应用逻辑：`scripts/apply.sh` 读取配置，用 python3 合并写入 `/etc/docker/daemon.json` 后重启 Docker
- 持久化钩子：`event/started` 在每次系统就绪时重新应用，解决 Unraid `/etc` 内存化导致重启丢失的问题
- 兼容性：Unraid 6.9+，依赖系统自带 python3

## 已知限制
- registry-mirrors 仅加速 Docker Hub（docker.io）拉取；GHCR / GCR 等需使用对应专属域名前缀拉取。
- 应用时会重启 Docker，容器会短暂中断。
- 部分镜像源需要注册获取专属地址（如阿里云），请使用「自定义」填写。
- 镜像源可用性随网络环境变化，若某个源不可用，可多填几个或换源。

## v2026.10.29.5 修复清单（本版为结构性重写）

对照两个真实可用插件（`libvirt.hotplug.usb` 与 `unraid-docker-folders-modern`）逐项排查后，发现并修复以下问题：

| # | 问题 | 后果 | 修复 |
|---|---|---|---|
| 1 | `.page` 内含完整 `<!DOCTYPE>/<html>/<head>/<body>` | Unraid 的 `.page` 是**嵌入**到已有页面框架里渲染的，重复包裹导致布局错乱 | 只输出内容片段 |
| 2 | `radio` 的 `onchange` 属性**引号未闭合** | 后续 HTML 被吞成属性值 → **页面空白** | 补齐引号 |
| 3 | 使用 `<INSTALL>` / `<REMOVE>` 元素 | 两者皆非 Unraid 标准结构，参考插件全都用 `<FILE Run="/bin/bash">` | 改为标准 `<FILE Run>` |
| 4 | 用 `<FILE Name>` 逐文件内联写码 | 无法保证权限与属主 | 改为打包 bundle(tgz) 解压安装 |
| 5 | 缺图标文件 | 菜单项显示不出图标 | 新增 `Dockermirror.png` 并在头部声明 `Icon=` |
| 6 | PHP 错误不可见 | 出错时白屏无法定位 | 页面顶部开启 `display_errors` |

`.page` 头部最终形态（与真实插件一致的多行格式）：
```
Menu="Utilities"
Title="Docker 镜像源"
Icon="Dockermirror.png"
Tag="globe"
Markdown="false"
---
```

> 已澄清：`launch` 属性**不是**菜单注册机制，它只是装完后一键打开页面的快捷方式；
> 真正注册菜单的是 `.page` 里的 `Menu=` 头。
> 另外"`.page` 文件名必须首字母大写"是误传——参考插件 `libvirthotplugusb.page` 就是小写且正常工作。

## 排错：安装后立即自检（推荐先看这个）

本版安装过程自带验证步骤，安装日志里会直接打印：
```
[dockermirror] bundle ready: /boot/config/plugins/dockermirror/dockermirror-2026.10.29.5.tgz (md5 ...)
[dockermirror] verifying installation in /usr/local/emhttp/plugins/dockermirror:
  ok      Dockermirror.page
  ok      Dockermirror.png
  ok      scripts/apply.sh
  ok      event/started
[dockermirror] page header:
Menu="Utilities"
```
- 全部 `ok` → 文件已正确落盘，按下面步骤刷新菜单即可。
- 出现 `MISSING` 或没有这段输出 → 把完整安装日志发我。

## 排错：菜单仍不出现

```bash
# 1. 确认文件真的落盘了（重点看 Dockermirror.page 是否存在、权限是否为 644）
ls -la /usr/local/emhttp/plugins/dockermirror/

# 2. 确认页面头部正确（第一行必须是 Menu="Utilities"）
head -6 /usr/local/emhttp/plugins/dockermirror/Dockermirror.page

# 3. 确认装的是本版
grep version= /var/log/plugins/dockermirror.plg

# 4. 强制 web 服务重扫菜单 + 清 nginx 缓存
/etc/rc.d/rc.nginx restart
rm -f /var/run/nginx.pid 2>/dev/null

# 5. 看 PHP 有没有因为本插件报错
tail -30 /var/log/phplog
```

然后**硬刷新浏览器**（Ctrl+Shift+R），去 **Settings → 用户实用工具（User Utilities）** 查看
（通常在 Settings 页**最底部**，需要滚到底）。

### 兜底：直接访问页面 URL
```
http://<你的服务器IP或tower>/Dockermirror
```
- 能正常显示 → 页面是好的，只是菜单链接没刷出来。
- 空白 → PHP 报错，本版已在页顶开启错误显示，刷新后应能看到具体错误，把它发我。

### 重装步骤（务必先卸载，清掉旧残留）
```bash
plugin remove dockermirror
plugin install /你存放的路径/dockermirror.plg
```

## 源码结构（可直接编辑后重新打包）
```
build/
  dockermirror/
    Dockermirror.page      # 设置页面（含头部元数据）
    Dockermirror.png       # 图标
    scripts/apply.sh       # 写入 daemon.json 并重启 Docker
    event/started          # 开机钩子
  gen_plg.py               # 打包脚本：build/ → tgz → base64 → dockermirror.plg
```
改完后执行 `python build/gen_plg.py` 即可重新生成 `.plg`（脚本内含 XML 与 CDATA 校验）。

