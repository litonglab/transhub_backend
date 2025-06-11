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
    if [ ! -d "$LOG_DIR" ]; then
        echo "📁 将要创建日志目录: $LOG_DIR"
        read -p "是否继续？(y/n): " confirm
        if [[ $confirm != [yY] ]]; then
            echo "❌ 用户取消创建目录"
            exit 1
        fi
        mkdir -p "$LOG_DIR" || { echo "❌ 无法创建日志目录: $LOG_DIR"; exit 1; }
        echo "✅ 日志目录已创建: $LOG_DIR"
    else
        echo "📁 日志目录已存在: $LOG_DIR"
    fi
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
        if ! supervisord -c "$CONFIG"; then
            echo "❌ supervisord 启动失败"
            exit 1
        fi
        echo "✅ 服务已启动，查看日志文件（$LOG_DIR）确认运行状态。"
        ;;
    stop)
        echo "🛑 停止服务..."
        
        # 先停止 dramatiq worker
        echo "⏳ 正在停止 dramatiq worker..."
        if ! supervisorctl -c "$CONFIG" stop dramatiq_worker; then
            echo "❌ 停止 dramatiq worker 失败"
            exit 1
        fi
        
        # 等待 dramatiq 任务完成
        echo "⏳ 等待 dramatiq 任务完成..."
        echo "请等待执行中的任务完成，预计最多需要几分钟，强行停止可能导致任务和成绩异常..."
        while true; do
            if ! pgrep -f "dramatiq app_backend.jobs.cctraining_job" > /dev/null; then
                break
            fi
            sleep 1
        done
        echo "✅ dramatiq worker 已停止"
        
        # 然后停止 flask 应用
        echo "⏳ 正在停止 flask 应用..."
        if ! supervisorctl -c "$CONFIG" stop flask_app; then
            echo "❌ 停止 flask 应用失败"
            exit 1
        fi
        
        # 最后关闭 supervisor
        if ! supervisorctl -c "$CONFIG" shutdown; then
            echo "❌ 关闭 supervisor 失败"
            exit 1
        fi
        
        echo "✅ 所有服务已停止"
        ;;
    status)
        echo "🔍 检查服务状态..."
        setup_environment
        display_config
        if ! supervisorctl -c "$CONFIG" status; then
            echo "❌ 获取服务状态失败"
            exit 1
        fi
        ;;
    restart)
        $0 stop
        echo "即将重启服务..."
        sleep 3
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