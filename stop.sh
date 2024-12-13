#!/bin/bash

# 关闭 Flask 应用
if [ -f flask_app.pid ]; then
  kill -9 $(cat flask_app.pid)
  rm flask_app.pid
  echo "Flask 应用已停止。"
else
  echo "Flask 应用的 PID 文件不存在。"
fi

# 关闭 16 个 dramatiq 进程
for i in {1..16}
do
  if [ -f rq_worker_$i.pid ]; then
    kill -9 $(cat rq_worker_$i.pid)
    rm rq_worker_$i.pid
    echo "RQ worker $i 已停止。"
  else
    echo "RQ worker $i 的 PID 文件不存在。"
  fi
done

echo "所有 RQ worker 已停止。"
