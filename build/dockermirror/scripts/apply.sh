#!/bin/bash
# dockermirror - 写入 Docker 镜像源配置
# 使用 mapfile + 循环，完全避免 sed/awk 转义问题
set +e

plugin="dockermirror"
CONFIG="/boot/config/plugins/$plugin/$plugin.cfg"
DAEMON="/etc/docker/daemon.json"
REMOVE=0

for arg in "$@"; do
  case "$arg" in
    --remove) REMOVE=1 ;;
  esac
done

# 读取配置
MIRRORS=""
if [ "$REMOVE" -eq 0 ] && [ -f "$CONFIG" ]; then
  eval "$(grep -E '^MIRRORS=' "$CONFIG" 2>/dev/null | head -1)"
  MIRRORS="${MIRRORS//\"/}"
fi

mkdir -p /etc/docker
[ ! -f "$DAEMON" ] && echo '{}' > "$DAEMON"
cp "$DAEMON" "${DAEMON}.bak" 2>/dev/null

# 构建镜像源数组项
MIRROR_ITEMS=""
if [ -n "$MIRRORS" ]; then
  IFS=',' read -ra ML <<< "$MIRRORS"
  n=0
  for m in "${ML[@]}"; do
    m=$(echo "$m" | xargs)
    [ -z "$m" ] && continue
    [ $n -gt 0 ] && MIRROR_ITEMS="$MIRROR_ITEMS, "
    MIRROR_ITEMS="$MIRROR_ITEMS\"$m\""
    n=$((n + 1))
  done
fi

# 用 mapfile 逐行读取，在最后一个 } 前插入新行
mapfile -t LINES < "$DAEMON"
NEW=""
LAST=$(( ${#LINES[@]} - 1 ))
for i in "${!LINES[@]}"; do
  LINE="${LINES[$i]}"
  # 跳过旧的 registry-mirrors 行
  case "$LINE" in
    *"registry-mirrors"*) continue ;;
  esac
  # 在最后一行（}）前插入
  if [ $i -eq $LAST ] && [ -n "$MIRROR_ITEMS" ]; then
    NEW="${NEW}  \"registry-mirrors\": [$MIRROR_ITEMS],
"
  fi
  NEW="${NEW}${LINE}
"
done

printf '%s' "$NEW" > "$DAEMON"

# 括号匹配验证
OPEN=$(grep -o '{' "$DAEMON" | wc -l)
CLOSE=$(grep -o '}' "$DAEMON" | wc -l)
if [ "$OPEN" -ne "$CLOSE" ]; then
  echo "JSON 格式错误，恢复备份"
  mv "${DAEMON}.bak" "$DAEMON"
  exit 1
fi

echo "已写入: [$MIRRORS]"

# 检查 Docker 是否运行
DOCKER_UP=0
pidof dockerd >/dev/null 2>&1 && DOCKER_UP=1

# 获取当前生效的镜像源
CURRENT=""
if [ $DOCKER_UP -eq 1 ]; then
  CURRENT=$(docker info --format '{{json .RegistryConfig.Mirrors}}' 2>/dev/null)
  CURRENT=$(echo "$CURRENT" | tr -d '[]" ')
fi

# 构建期望列表（排序，去末尾逗号）
EXPECT=""
[ -n "$MIRRORS" ] && EXPECT=$(echo "$MIRRORS" | tr ',' '\n' | sort | tr '\n' ',' | sed 's/,$//')

# 决定是否重启
if [ $DOCKER_UP -eq 0 ]; then
  echo "Docker 未运行，仅写入配置"
elif [ -z "$EXPECT" ]; then
  echo "清除镜像源，重启 Docker..."
  /etc/rc.d/rc.docker restart
elif [ "$CURRENT" != "$EXPECT" ]; then
  echo "镜像源变更: [$CURRENT] -> [$EXPECT]"
  echo "重启 Docker..."
  /etc/rc.d/rc.docker restart
else
  echo "镜像源已匹配，无需重启"
fi

rm -f "${DAEMON}.bak"
exit 0
