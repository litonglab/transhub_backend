#!/bin/bash
PID_FILE="/home/liuwei/transhub_backend/dramatiq.pid"  # 替换为实际 PID 文件路径
APP_DIR="/home/liuwei/transhub_backend/"          # 替换为应用目录
LOG_FILE="/home/liuwei/transhub_backend/dramatiq_monitor.log" 


export PATH="/usr/local/bin:/usr/bin:/bin"  # 确保编译器路径正确
export CXXFLAGS="-fPIC"                     # 强制启用位置无关代码
export LD_LIBRARY_PATH="/usr/local/lib:$LD_LIBRARY_PATH"


# 检查 PID 文件是否存在
if [ -f "$PID_FILE" ]; then
  PID=$(cat "$PID_FILE")
  # 检查进程是否存在
  if ! kill -0 "$PID" 2>/dev/null; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - 进程 $PID 已停止，正在重启..." >> "$LOG_FILE"
    cd "$APP_DIR" || exit 1
    setsid /home/liuwei/.local/bin/dramatiq --processes 8 app_backend.jobs.cctraining_job & echo $! > "$PID_FILE"
  else
    echo "$(date '+%Y-%m-%d %H:%M:%S') - 进程 $PID 运行正常。" >> "$LOG_FILE"
  fi
else
  echo "$(date '+%Y-%m-%d %H:%M:%S') - PID 文件不存在，正在启动新进程..." >> "$LOG_FILE"
  cd "$APP_DIR" || exit 1
  setsid dramatiq --processes 8 app_backend.jobs.cctraining_job & echo $! > "$PID_FILE"
fi