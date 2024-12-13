#!/bin/bash

# 函数用于安全杀死进程组
kill_process_group() {
    if [ -f "$1" ]; then
        PID=$(cat "$1")
        if kill -0 $PID 2>/dev/null; then
            PGID=$(ps -o pgid= -p $PID | grep -o '[0-9]*')
            echo "正在杀死进程组 $PGID（来自 $1）..."
            kill -9 -$PGID
            rm -f "$1"
            echo "进程组 $PGID 已被杀死。"
        else
            echo "进程 $PID 不存在或已被终止。"
            rm -f "$1"
        fi
    else
        echo "PID 文件 $1 不存在。"
    fi
}

# 杀死 Flask、Dramatiq 和 Gunicorn 的进程组
kill_process_group flask_app.pid
kill_process_group dramatiq.pid
kill_process_group gunicorn.pid

#!/bin/bash

# 函数用于安全杀死进程组
kill_process_group() {
    if [ -f "$1" ]; then
        PID=$(cat "$1")
        if kill -0 $PID 2>/dev/null; then
            PGID=$(ps -o pgid= -p $PID | grep -o '[0-9]*')
            echo "正在杀死进程组 $PGID（来自 $1）..."
            kill -9 -$PGID
            rm -f "$1"
            echo "进程组 $PGID 已被杀死。"
        else
            echo "进程 $PID 不存在或已被终止。"
            rm -f "$1"
        fi
    else
        echo "PID 文件 $1 不存在。"
    fi
}

# 杀死 Flask、Dramatiq 和 Gunicorn 的进程组
kill_process_group flask_app.pid
kill_process_group dramatiq.pid
kill_process_group gunicorn.pid




echo "所有进程组已被强行关闭。"
