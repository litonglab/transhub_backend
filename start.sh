#!/bin/bash

# 启动 Flask 应用并将 PID 保存到 flask_app.pid
export FLASK_APP=app
flask run & echo $! > flask_app.pid

# 启动 16 个 RQ worker 并将 PID 保存到 rq_worker_<num>.pid 文件
for i in {1..16}
do
  flask rq worker & echo $! > rq_worker_$i.pid
done

echo "Flask 应用和 16 个 RQ worker 已启动，并将 PID 保存到相应的文件中。"
