#!/bin/bash
# dockermirror - 写入 Docker registry-mirrors 配置
# 纯 bash 实现，不依赖 python3/sed 转义，适配 Unraid 7.x
#
# 用法:
#   apply.sh              应用配置，必要时异步重启 Docker（页面点击时用）
#   apply.sh --no-restart 仅写入配置，不重启 Docker（开机钩子/安装时用）
#
set +e

PLUGIN="dockermirror"
CONFIG="/boot/config/plugins/${PLUGIN}/${PLUGIN}.cfg"
DAEMON="/etc/docker/daemon.json"

RESTART=1
for arg in "$@"; do
  case "$arg" in
    --no-restart) RESTART=0 ;;
  esac
done

# ---------- 1. 读取插件配置 ----------
MIRRORS=""
if [ -f "$CONFIG" ]; then
  # 兼容 MIRRORS="a,b" / MIRRORS=a,b / MIRRORS='a,b'
  LINE=$(grep -E '^[[:space:]]*MIRRORS[[:space:]]*=' "$CONFIG" 2>/dev/null | head -1)
  if [ -n "$LINE" ]; then
    MIRRORS="${LINE#*=}"
    MIRRORS="${MIRRORS%\"}"   # 去尾部引号
    MIRRORS="${MIRRORS#\"}"   # 去头部引号
    MIRRORS="${MIRRORS%\'}"
    MIRRORS="${MIRRORS#\'}"
    MIRRORS=$(echo "$MIRRORS" | tr -d '[:space:]')  # 去所有空白
  fi
fi

# ---------- 2. 构建 JSON 数组片段 ----------
MIRROR_ITEMS=""
if [ -n "$MIRRORS" ]; then
  OLD_IFS="$IFS"
  IFS=','
  set -- $MIRRORS
  IFS="$OLD_IFS"
  n=0
  for m in "$@"; do
    [ -z "$m" ] && continue
    if [ $n -gt 0 ]; then MIRROR_ITEMS="${MIRROR_ITEMS}, "; fi
    MIRROR_ITEMS="${MIRROR_ITEMS}\"${m}\""
    n=$((n + 1))
  done
fi

# ---------- 3. 备份并重建 daemon.json ----------
# 说明：采用「重建」而非「插入」，可彻底规避 trailing comma 与 sed 对 URL 斜杠的转义问题。
# 保留原有简单键值对行，仅增删 registry-mirrors，输出保证是合法 JSON。
mkdir -p /etc/docker
if [ ! -f "$DAEMON" ]; then echo '{}' > "$DAEMON"; fi
cp -f "$DAEMON" "${DAEMON}.dmbak" 2>/dev/null

# 收集原有配置项（跳过 registry-mirrors、括号、空行），去掉尾部逗号
OTHER=""
while IFS= read -r line; do
  case "$line" in
    *'"registry-mirrors"'*) continue ;;
  esac
  # 去除首尾空白与行尾逗号
  trimmed="${line#"${line%%[![:space:]]*}"}"   # 去前导空白
  trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"  # 去尾部空白
  trimmed="${trimmed%,}"                        # 去尾部逗号
  case "$trimmed" in
    '{' | '}' | '' | '}'*'{'*) continue ;;
    '"'*':'*)
      if [ -n "$OTHER" ]; then OTHER="${OTHER},
"; fi
      OTHER="${OTHER}  ${trimmed}" ;;
  esac
done < "$DAEMON"

# 组装最终内容
ITEMS="$OTHER"
if [ -n "$MIRROR_ITEMS" ]; then
  if [ -n "$ITEMS" ]; then ITEMS="${ITEMS},
"; fi
  ITEMS="${ITEMS}  \"registry-mirrors\": [${MIRROR_ITEMS}]"
fi

if [ -n "$ITEMS" ]; then
  OUT="{
${ITEMS}
}"
else
  OUT="{}"
fi

printf '%s\n' "$OUT" > "$DAEMON"

# ---------- 4. 校验 JSON 括号配对 ----------
OPEN=$(tr -cd '{' < "$DAEMON" | wc -c)
CLOSE=$(tr -cd '}' < "$DAEMON" | wc -c)
if [ "$OPEN" -ne "$CLOSE" ] || [ "$OPEN" -eq 0 ]; then
  # 回滚
  if [ -f "${DAEMON}.dmbak" ]; then mv -f "${DAEMON}.dmbak" "$DAEMON"; fi
  echo "[dockermirror] 错误：daemon.json 格式损坏，已回滚"
  exit 1
fi
rm -f "${DAEMON}.dmbak"

if [ -n "$MIRRORS" ]; then
  echo "[dockermirror] 已写入镜像源: ${MIRRORS}"
else
  echo "[dockermirror] 已清除镜像源（直连 Docker Hub）"
fi

# ---------- 5. 决定是否重启 Docker ----------
if [ "$RESTART" -eq 0 ]; then
  echo "[dockermirror] 仅写入配置，未重启 Docker"
  exit 0
fi

# Docker 是否在运行
if ! pidof dockerd >/dev/null 2>&1; then
  echo "[dockermirror] Docker 未运行，配置将在下次启动时生效"
  exit 0
fi

# 读取当前生效的镜像源
CURRENT=$(docker info --format '{{json .RegistryConfig.Mirrors}}' 2>/dev/null)
CURRENT=$(printf '%s' "$CURRENT" | tr -d '[]" ' | tr ',' '\n' | grep -v '^$' | sort | tr '\n' ',' | sed 's/,$//')

# 期望值（排序后比较，忽略顺序）
EXPECT=""
if [ -n "$MIRRORS" ]; then
  EXPECT=$(printf '%s' "$MIRRORS" | tr ',' '\n' | sort | tr '\n' ',' | sed 's/,$//')
fi

if [ "$CURRENT" = "$EXPECT" ]; then
  echo "[dockermirror] 镜像源已是最新，无需重启 Docker"
  exit 0
fi

echo "[dockermirror] 镜像源变更 [${CURRENT}] -> [${EXPECT}]，正在后台重启 Docker..."

# 异步重启：不阻塞页面（避免 WebGUI 白屏/超时）
# rc.docker 自带 stop->start，用 nohup 脱离当前进程组
nohup /etc/rc.d/rc.docker restart >/dev/null 2>&1 &

exit 0
