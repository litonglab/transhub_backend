#!/bin/bash

# 启动 Flask 应用并将 PID 保存到 flask_app.pid
export FLASK_APP=run:app
export FLASK_ENV=production
export FLASK_DEBUG=0
flask run --host=0.0.0.0 --port=54321 & echo $! > flask_app.pid

# 启动 dramatiq 并设置新的进程组
setsid dramatiq --processes 8 app_backend.jobs.cctraining_job & echo $! > dramatiq.pid

# 启动 Gunicorn 并设置新的进程组
# setsid gunicorn -w 1 -b 127.0.0.1:12345 wsgi:application & echo $! > gunicorn.pid

echo "Flask 应用、Dramatiq 和 16 个 RQ worker 已启动。"
