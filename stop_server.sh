#!/bin/bash
# 停止ASR API服务

echo "正在停止ASR API服务..."

# 查找并停止运行在8000端口的进程
PORT=8000
PIDS=$(lsof -ti:$PORT 2>/dev/null)

if [ -z "$PIDS" ]; then
    echo "✓ 没有发现运行在端口 $PORT 的服务"
    exit 0
fi

# 停止进程
for PID in $PIDS; do
    echo "停止进程 $PID..."
    kill -9 $PID 2>/dev/null
done

# 等待一下确保进程已停止
sleep 1

# 再次检查
REMAINING=$(lsof -ti:$PORT 2>/dev/null)
if [ -z "$REMAINING" ]; then
    echo "✓ 服务已成功停止"
else
    echo "⚠ 警告: 仍有进程运行在端口 $PORT"
    echo "进程ID: $REMAINING"
    exit 1
fi

