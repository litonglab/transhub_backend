#!/bin/bash
# 轻量级启动脚本：通过环境变量集成配置

CONFIG="supervisor.ini"
export APP_ENV="production"

setup_environment() {
    # 设置环境
    export APP_ENV=${APP_ENV:-"development"}
    echo "🌍 当前环境: $APP_ENV"

    # 确保在项目根目录下执行
    PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    cd "$PROJECT_ROOT" || { echo "❌ 无法进入项目目录: $PROJECT_ROOT"; exit 1; }

    # 加载环境变量配置
    if [ -f ".env.$APP_ENV" ]; then
        echo "📝 加载环境变量配置: .env.$APP_ENV"
        set -a
        source ".env.$APP_ENV"
        set +a
    else
        echo "⚠️ 警告: 未找到环境配置文件 .env.$APP_ENV"
        exit 1
    fi

    # 确保日志目录存在
    mkdir -p "$LOG_DIR" || { echo "❌ 无法创建日志目录: $LOG_DIR"; exit 1; }
    echo "📁 日志目录已创建: $LOG_DIR"
}

display_config() {
  # 输出配置信息
    echo "✅ 配置已加载:"
    echo "  APP_ENV  = $APP_ENV"
    echo "  LOG_DIR  = $LOG_DIR"
    echo "  GUNICORN = $GUNICORN_ADDRESS(WORKERS:$GUNICORN_WORKERS, THREADS:$GUNICORN_THREADS)"
    echo "  DRAMATIQ = (PROCESSES: $DRAMATIQ_PROCESSES, THREADS: $DRAMATIQ_THREADS)"
}

case "$1" in
    start)
        echo "🚀 启动服务..."
        setup_environment
        display_config
        supervisord -c "$CONFIG"
        echo "✅ 服务已启动，查看日志文件（$LOG_DIR）确认运行状态。"
        ;;
    stop)
        echo "🛑 停止服务..."
        supervisorctl -c "$CONFIG" shutdown
        ;;
    status)
        echo "🔍 检查服务状态..."
        setup_environment
        display_config
        supervisorctl -c "$CONFIG" status
        ;;
    restart)
        $0 stop
        sleep 10
        $0 start
        ;;
    config)
        setup_environment
        display_config
        ;;
    *)
        echo "使用方法: $0 {start|stop|status|restart|config}"
        exit 1
esac