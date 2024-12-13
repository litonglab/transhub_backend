#!/bin/bash

# 启动 Flask 应用并将 PID 保存到 flask_app.pid
export FLASK_APP=run:app
export FLASK_ENV=production
export FLASK_DEBUG=0
flask run & echo $! > flask_app.pid

# 启动 16 个 RQ worker 并将 PID 保存到 rq_worker_<num>.pid 文件
dramatiq -processes 16 app_backend.jobs.cctraining_job & echo $! > rq_worker_1.pid
echo "Flask 应用和 16 个 RQ worker 已启动，并将 PID 保存到相应的文件中。"
