# dockermirror — GitHub 部署与安装说明

## 本次修复要点

| 问题 | 原因 | 修复 |
|------|------|------|
| 安装/卸载弹出「操作将在后台继续进行」 | 旧版安装脚本内含 `nginx restart`、`python3` 调用与 base64 解码，耗时较长触发 Unraid 后台模式 | 安装/卸载脚本精简为**纯文件操作**，不重启任何服务、不调用 python3，立即完成 |
| 安装插件后 Docker 被重启、容器起不来 | 旧版在 install/remove 阶段操作 Docker | 安装、卸载、开机**均不重启 Docker**；只有点击「保存并应用」且镜像源确实变化时才重启 |
| 保存后页面空白 | `apply.sh` 同步等待 Docker 重启，PHP 超时 | Docker 重启改为**异步后台执行**，脚本立即返回 |
| 配置写了但不生效 | `python3` 在 Unraid 7.3.2 不存在；`sed` 遇到 URL 里的 `/` 报错 | 全部改为**纯 bash** 处理，采用「重建 JSON」策略，彻底规避转义问题 |
| 开机后镜像源失效 | `event/started` 时 Docker 已启动，写配置需重启才生效 | 改用 `event/starting`（Docker 启动**前**写入），开机即生效且零重启 |

## 一、部署到 GitHub

### 1. 创建仓库并推送

```bash
cd dockermirror
git init
git add .
git commit -m "Initial commit: dockermirror plugin"
git branch -M main
git remote add origin https://github.com/<你的用户名>/dockermirror.git
git push -u origin main
```

### 2. 修改仓库地址

编辑 `build_plugin.py` 顶部的三个变量：

```python
GITHUB_USER   = "<你的用户名>"
GITHUB_REPO   = "dockermirror"
GITHUB_BRANCH = "main"
```

### 3. 发布 Release

```bash
python build_plugin.py              # 本地生成 dist/ 产物
git tag 2026.10.30
git push origin 2026.10.30
```

推送 tag 后 GitHub Actions 会自动：
- 打包 `dockermirror-2026.10.30.tgz`
- 计算 md5 并写入 `dockermirror.plg`
- 把更新后的 plg 提交回仓库
- 创建 Release 并上传 tgz

> 如果不用 CI，也可手动：在 GitHub 网页新建 Release（tag 填 `2026.10.30`），上传 `dist/dockermirror-2026.10.30.tgz`，然后本地运行 `python build_plugin.py` 并把生成的 `dockermirror.plg` 推到仓库。

## 二、Unraid 安装

### 方式 A：通过 GitHub（推荐，支持后续更新）

Unraid WebGUI → **插件** → **安装插件**，粘贴：

```
https://raw.githubusercontent.com/<你的用户名>/dockermirror/main/dockermirror.plg
```

### 方式 B：本地离线安装

把 `dist/dockermirror-local.plg` 上传到 Unraid，在「安装插件」里填本地路径，例如：

```
/boot/config/plugins/dockermirror-local.plg
```

此版本把插件文件以 base64 内嵌，无需访问外网。

## 三、使用

安装后进入：**设置 → 用户程序 → Docker 镜像源切换**。

- 选择预设镜像源（DaoCloud / 腾讯云 / 网易 / 百度 / 毫秒 / 轩辕）
- 或填写自定义地址（每行一个，支持多个）
- 点击「保存并应用」：若镜像源有变化，Docker 会在后台重启（十几秒），刷新页面即可看到生效
- 点击「恢复默认设置」：清除镜像源，直连 Docker Hub

配置保存在 U 盘 `/boot/config/plugins/dockermirror/dockermirror.cfg`，开机自动写入，重启不丢失。

## 四、验证是否生效

SSH 登录 Unraid 后执行：

```bash
# 查看配置文件
cat /boot/config/plugins/dockermirror/dockermirror.cfg

# 查看 daemon.json
cat /etc/docker/daemon.json

# 查看 Docker 实际生效的镜像源
docker info --format '{{json .RegistryConfig.Mirrors}}'
```

## 五、目录结构

```
dockermirror/
├── src/usr/local/emhttp/plugins/dockermirror/   # 插件源码（打包为 tgz）
│   ├── Dockermirror.page      # 设置页面
│   ├── Dockermirror.png       # 图标
│   ├── README.md              # 插件列表说明
│   ├── default.cfg            # 默认配置
│   ├── scripts/apply.sh       # 核心：写 daemon.json + 按需重启 Docker
│   └── event/
│       ├── starting           # 开机钩子（Docker 启动前写入，零重启）
│       └── started            # 兜底钩子
├── build_plugin.py            # 构建脚本
├── dockermirror.plg           # GitHub 部署版（仓库根，供 raw 引用）
└── dist/                      # 构建产物
    ├── dockermirror-<VER>.tgz
    ├── dockermirror.plg
    └── dockermirror-local.plg
```
