#!/bin/bash
# 轻量级启动脚本：通过环境变量集成配置

CONFIG="supervisor.ini"

export_python_config() {
    # 确保在项目根目录下执行
    PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    cd "$PROJECT_ROOT" || { echo "❌ 无法进入项目目录: $PROJECT_ROOT"; exit 1; }

    # 安全导出所有配置变量
    eval "$(python3 -c "from app_backend.config import export_config2env; export_config2env()")"

    # 输出验证
    echo "✅ 配置已加载:"
    echo "  BASEDIR  = $BASEDIR"
    echo "  LOG_DIR  = $LOG_DIR"
    echo "  GUNICORN = $GUNICORN_ADDRESS (workers: $GUNICORN_WORKERS, threads: $GUNICORN_THREADS)"
    echo "  DRAMATIQ = (processes: $DRAMATIQ_PROCESSES, threads: $DRAMATIQ_THREADS)"
}

setup_environment() {
    # 确保日志目录存在
    mkdir -p "$LOG_DIR" || { echo "❌ 无法创建日志目录: $LOG_DIR"; exit 1; }
    echo "📁 日志目录已创建: $LOG_DIR"

    # 设置其他相关环境变量
#    export VENV_PATH="$BASEDIR/.venv"
}

case "$1" in
    start)
        echo "启动服务..."
        export_python_config
        setup_environment
        supervisord -c "$CONFIG"
        ;;
    stop)
        echo "停止服务..."
        supervisorctl -c "$CONFIG" shutdown
        ;;
    status)
        export_python_config
        supervisorctl -c "$CONFIG" status
        ;;
    restart)
        $0 stop
        sleep 2
        $0 start
        ;;
    config)
        export_python_config
        ;;
    *)
        echo "使用方法: $0 {start|stop|status|restart|config}"
        exit 1
esac