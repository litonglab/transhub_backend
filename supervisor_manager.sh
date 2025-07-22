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
    echo "  DRAMATIQ = (CC_TRAINING: P-$DRAMATIQ_PROCESSES T-$DRAMATIQ_THREADS, GRAPH: P-1 T-$DRAMATIQ_THREADS_GRAPH, SVG2PNG: P-1 T-1)"
}

check_process_status() {
    local max_attempts=30
    local check_interval=2
    local attempt=0
    
    echo "🔍 检查进程启动状态..."
    
    while [ $attempt -lt $max_attempts ]; do
        # 获取当前状态
        local status_output=$(supervisorctl -c "$CONFIG" status 2>/dev/null)
        
        if [ $? -ne 0 ]; then
            echo "❌ 无法连接到supervisor，可能未正确启动"
            return 1
        fi
        
        # 检查所有程序状态
        local flask_status=$(echo "$status_output" | grep "flask_app" | awk '{print $2}')
        local dramatiq_cc_status=$(echo "$status_output" | grep "dramatiq_worker-cc_training" | awk '{print $2}')
        local dramatiq_graph_status=$(echo "$status_output" | grep "dramatiq_worker-graph" | awk '{print $2}')
        local dramatiq_svg2png_status=$(echo "$status_output" | grep "dramatiq_worker-svg2png" | awk '{print $2}')
        
        echo "  [$((attempt+1))/$max_attempts] Flask: $flask_status, Dramatiq(cc): $dramatiq_cc_status, Dramatiq(graph): $dramatiq_graph_status, Dramatiq(svg2png): $dramatiq_svg2png_status"
        
        # 如果所有进程都在运行，则成功
        if [[ "$flask_status" == "RUNNING" && "$dramatiq_cc_status" == "RUNNING" && "$dramatiq_graph_status" == "RUNNING" && "$dramatiq_svg2png_status" == "RUNNING" ]]; then
            echo "✅ 所有进程启动成功！"
            echo "📊 当前状态:"
            supervisorctl -c "$CONFIG" status
            return 0
        fi
        
        # 检查是否有进程启动失败
        if [[ "$flask_status" == "FATAL" || "$dramatiq_cc_status" == "FATAL" || "$dramatiq_graph_status" == "FATAL" || "$dramatiq_svg2png_status" == "FATAL" ]]; then
            echo "❌ 发现进程启动失败！"
            echo "📊 详细状态:"
            supervisorctl -c "$CONFIG" status
            show_startup_errors
            return 1
        fi
        
        # 如果还在启动中，继续等待
        if [[ "$flask_status" == "STARTING" || "$dramatiq_cc_status" == "STARTING" || "$dramatiq_graph_status" == "STARTING" || "$dramatiq_svg2png_status" == "STARTING" ]]; then
            sleep $check_interval
            attempt=$((attempt + 1))
            continue
        fi
        
        # 其他状态也继续等待一会
        sleep $check_interval
        attempt=$((attempt + 1))
    done
    
    echo "⚠️ 等待超时，进程可能未能正常启动"
    echo "📊 当前状态:"
    supervisorctl -c "$CONFIG" status
    show_startup_errors
    return 1
}

show_startup_errors() {
    echo ""
    echo "🔍 排查启动问题的建议:"
    echo "1. 查看supervisor主日志:"
    echo "   tail -f $LOG_DIR/supervisord.log"
    echo ""
    echo "2. 查看Flask应用日志:"
    echo "   tail -f $LOG_DIR/flask_app.err.log"
    echo "   tail -f $LOG_DIR/flask_app.out.log"
    echo ""
    echo "3. 查看Dramatiq任务队列日志:"
    echo "   tail -f $LOG_DIR/dramatiq-cc_training.err.log"
    echo "   tail -f $LOG_DIR/dramatiq-cc_training.out.log"
    echo "   tail -f $LOG_DIR/dramatiq-graph.err.log"
    echo "   tail -f $LOG_DIR/dramatiq-graph.out.log"
    echo "   tail -f $LOG_DIR/dramatiq-svg2png.err.log"
    echo "   tail -f $LOG_DIR/dramatiq-svg2png.out.log"
    echo ""
    echo "4. 检查端口占用情况:"
    echo "   lsof -i :$(echo $GUNICORN_ADDRESS | cut -d':' -f2)"
    echo ""
    echo "5. 检查Python环境和依赖:"
    echo "   which python"
    echo "   pip list | grep -E '(flask|gunicorn|dramatiq)'"
    echo ""
    echo "6. 手动测试启动命令:"
    echo "   gunicorn run:app -w $GUNICORN_WORKERS --threads $GUNICORN_THREADS -b $GUNICORN_ADDRESS"
    echo "   dramatiq app_backend.jobs.cctraining_job --processes $DRAMATIQ_PROCESSES --threads $DRAMATIQ_THREADS --queues cc_training"
    echo "   dramatiq app_backend.jobs.graph_job --processes 1 --threads $DRAMATIQ_THREADS_GRAPH --queues graph"
    echo "   dramatiq app_backend.jobs.graph_job --processes 1 --threads 1 --queues svg2png"
}

case "$1" in
    start)
        echo "🚀 启动服务..."
        setup_environment
        display_config
        
        # 检查supervisor是否已经在运行
        if pgrep -f "supervisord.*$CONFIG" > /dev/null; then
            echo "⚠️ 检测到supervisor已在运行，尝试重新加载配置..."
            supervisorctl -c "$CONFIG" reread
            supervisorctl -c "$CONFIG" update
        else
            # 启动supervisor
            if ! supervisord -c "$CONFIG"; then
                echo "❌ supervisord 启动失败"
                echo "💡 请检查配置文件和日志目录权限"
                exit 1
            fi
        fi
        
        # 等待并检查进程启动状态
        if check_process_status; then
            echo "✅ 服务已成功启动并运行正常！"
            echo "📋 管理命令提示:"
            echo "  查看状态: $0 status"
            echo "  停止服务: $0 stop"
            echo "  重启服务: $0 restart"
            echo "  查看配置: $0 config"
            echo "  查看日志: $0 logs"
        else
            echo "由于服务启动失败，正在关闭已启动的服务..."
            $0 stop
            echo "❌ 服务启动过程中出现问题，请查看上述排查建议"
            echo "➡️ 使用 '$0 logs' 查看日志文件"
            exit 1
        fi
        ;;
    stop)
        echo "🛑 停止服务..."
        
        # 先停止 dramatiq worker
        echo "⏳ 正在停止所有 dramatiq worker..."
        if ! supervisorctl -c "$CONFIG" stop dramatiq_worker-cc_training dramatiq_worker-graph dramatiq_worker-svg2png; then
            echo "❌ 停止 dramatiq worker 失败"
            exit 1
        fi
        
        # 等待 dramatiq 任务完成
        echo "⏳ 等待 dramatiq 任务完成..."
        echo "请等待执行中的任务完成，预计最多需要几分钟，强行停止可能导致任务和成绩异常..."
        while true; do
            if ! pgrep -f "dramatiq app_backend.jobs" > /dev/null; then
                break
            fi
            sleep 1
        done
        echo "✅ 所有 dramatiq worker 已停止"
        
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
        
        # 检查supervisor进程
        if ! pgrep -f "supervisord.*$CONFIG" > /dev/null; then
            echo "❌ supervisor进程未运行"
            exit 1
        fi
        
        # 显示端口占用情况
        echo ""
        echo "🌐 端口占用情况:"
        port=$(echo "$GUNICORN_ADDRESS" | cut -d':' -f2)
        if lsof -i :$port 2>/dev/null | grep -q "LISTEN"; then
            echo "  ✅ 端口 $port 正在监听"
            lsof -i :$port 2>/dev/null
        else
            echo "  ❌ 端口 $port 未在监听"
        fi
        
        # 显示进程信息
        echo ""
        echo "🔄 相关进程:"
        echo "  Gunicorn进程:"
        pgrep -f "gunicorn.*run:app" -l 2>/dev/null || echo "    未找到gunicorn进程"
        echo "  Dramatiq进程:"
        pgrep -f "dramatiq.*app_backend.jobs" -l 2>/dev/null || echo "    未找到dramatiq进程"
        
        echo "📊 详细状态信息:"
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
    logs)
        setup_environment
        echo "📋 查看日志文件..."
        echo "请选择要查看的日志:"
        echo "1) Supervisor主日志"
        echo "2) App日志"
        echo "3) Flask应用错误日志"
        echo "4) Flask应用输出日志"
        echo "5) Flask access日志"
        echo "6) Dramatiq(cc_training)错误日志"
        echo "7) Dramatiq(cc_training)输出日志"
        echo "8) Dramatiq(graph)错误日志"
        echo "9) Dramatiq(graph)输出日志"
        echo "10) Dramatiq(svg2png)错误日志"
        echo "11) Dramatiq(svg2png)输出日志"
        echo "12) 查看所有最新错误日志"

        read -p "请选择 (1-12): " choice

        case $choice in
            1) tail -f "$LOG_DIR/supervisord.log" ;;
            2) tail -f "$LOG_DIR/app.log" ;;
            3) tail -f "$LOG_DIR/flask_app.err.log" ;;
            4) tail -f "$LOG_DIR/flask_app.out.log" ;;
            5) tail -f "$LOG_DIR/flask_app.access.log" ;;
            6) tail -f "$LOG_DIR/dramatiq-cc_training.err.log" ;;
            7) tail -f "$LOG_DIR/dramatiq-cc_training.out.log" ;;
            8) tail -f "$LOG_DIR/dramatiq-graph.err.log" ;;
            9) tail -f "$LOG_DIR/dramatiq-graph.out.log" ;;
            10) tail -f "$LOG_DIR/dramatiq-svg2png.err.log" ;;
            11) tail -f "$LOG_DIR/dramatiq-svg2png.out.log" ;;
            12) 
                echo "显示所有错误日志的最后20行:"
                echo "=== Supervisor主日志 ==="
                tail -20 "$LOG_DIR/supervisord.log" 2>/dev/null || echo "日志文件不存在"
                echo ""
                echo "=== Flask应用错误日志 ==="
                tail -20 "$LOG_DIR/flask_app.err.log" 2>/dev/null || echo "日志文件不存在"
                echo ""
                echo "=== Dramatiq(cc_training)错误日志 ==="
                tail -20 "$LOG_DIR/dramatiq-cc_training.err.log" 2>/dev/null || echo "日志文件不存在"
                echo ""
                echo "=== Dramatiq(graph)错误日志 ==="
                tail -20 "$LOG_DIR/dramatiq-graph.err.log" 2>/dev/null || echo "日志文件不存在"
                echo ""
                echo "=== Dramatiq(svg2png)错误日志 ==="
                tail -20 "$LOG_DIR/dramatiq-svg2png.err.log" 2>/dev/null || echo "日志文件不存在"
                ;;
            *) echo "❌ 无效选择" ;;
        esac
        ;;
    *)
        echo "使用方法: $0 {start|stop|status|restart|config|logs}"
        exit 1
esac
