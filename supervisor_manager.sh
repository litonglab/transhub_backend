#!/bin/bash
# 轻量级启动脚本：通过环境变量集成配置

CONFIG="supervisor.ini"
export APP_ENV="production"

# 解析supervisor.ini配置文件，获取程序列表和日志文件路径
parse_supervisor_config() {
    local config_file="$1"
    
    if [ ! -f "$config_file" ]; then
        echo "❌ 配置文件不存在: $config_file"
        exit 1
    fi
    
    # 定义环境变量替换规则数组
    local env_vars=(
        "%(ENV_GUNICORN_WORKERS)s:$GUNICORN_WORKERS"
        "%(ENV_GUNICORN_THREADS)s:$GUNICORN_THREADS"
        "%(ENV_GUNICORN_ADDRESS)s:$GUNICORN_ADDRESS"
        "%(ENV_DRAMATIQ_PROCESSES)s:$DRAMATIQ_PROCESSES"
        "%(ENV_DRAMATIQ_THREADS)s:$DRAMATIQ_THREADS"
        "%(ENV_DRAMATIQ_THREADS_GRAPH)s:$DRAMATIQ_THREADS_GRAPH"
        "%(ENV_LOG_DIR)s:$LOG_DIR"
    )

    replace_env_vars() {
        local input="$1"
        for env_var in "${env_vars[@]}"; do
            local pattern="${env_var%%:*}"
            local value="${env_var#*:}"
            input="${input//$pattern/$value}"
        done
        echo "$input"
    }
    
    # 获取所有 [program:xxx] 段的程序名
    SUPERVISOR_PROGRAMS=($(grep '^\[program:' "$config_file" | sed 's/\[program:\(.*\)\]/\1/' | grep -v '^#'))
    
    # 分类程序
    FLASK_PROGRAMS=()
    DRAMATIQ_PROGRAMS=()
    
    # 创建关联数组存储日志文件路径和命令
    declare -gA PROGRAM_ERR_LOGS
    declare -gA PROGRAM_OUT_LOGS
    declare -gA PROGRAM_ACCESS_LOGS
    declare -gA PROGRAM_COMMANDS
    
    for program in "${SUPERVISOR_PROGRAMS[@]}"; do
        if [[ "$program" == *"flask"* ]] || [[ "$program" == *"app"* ]]; then
            FLASK_PROGRAMS+=("$program")
        elif [[ "$program" == *"dramatiq"* ]] || [[ "$program" == *"worker"* ]]; then
            DRAMATIQ_PROGRAMS+=("$program")
        fi
        
        # 解析该程序的日志文件路径
        local program_section_started=false
        local current_program=""
        
        while IFS= read -r line; do
            # 检查是否进入了当前程序的配置段
            if [[ "$line" =~ ^\[program:$program\] ]]; then
                program_section_started=true
                current_program="$program"
                continue
            fi
            
            # 如果遇到新的段，停止解析当前程序
            if [[ "$line" =~ ^\[.*\] ]] && [[ "$program_section_started" == true ]]; then
                break
            fi
            
            # 在当前程序段内解析日志文件路径和命令
            if [[ "$program_section_started" == true ]]; then
                if [[ "$line" =~ ^stderr_logfile[[:space:]]*=[[:space:]]*(.+)$ ]]; then
                    local err_log_path="${BASH_REMATCH[1]}"
                    err_log_path=$(replace_env_vars "$err_log_path")
                    PROGRAM_ERR_LOGS["$program"]="$err_log_path"
                elif [[ "$line" =~ ^stdout_logfile[[:space:]]*=[[:space:]]*(.+)$ ]]; then
                    local out_log_path="${BASH_REMATCH[1]}"
                    out_log_path=$(replace_env_vars "$out_log_path")
                    PROGRAM_OUT_LOGS["$program"]="$out_log_path"
                elif [[ "$line" =~ ^command[[:space:]]*=[[:space:]]*(.+)$ ]]; then
                    local command="${BASH_REMATCH[1]}"
                    command=$(replace_env_vars "$command")
                    PROGRAM_COMMANDS["$program"]="$command"
                elif [[ "$line" =~ --access-logfile[[:space:]]+([^[:space:]]+) ]]; then
                    local access_log_path="${BASH_REMATCH[1]}"
                    access_log_path=$(replace_env_vars "$access_log_path")
                    PROGRAM_ACCESS_LOGS["$program"]="$access_log_path"
                fi
            fi
        done < "$config_file"
    done
    
    # 调试输出
    echo "🔍 检测到的程序列表:"
    echo "  Flask程序: ${FLASK_PROGRAMS[*]}"
    echo "  Dramatiq程序: ${DRAMATIQ_PROGRAMS[*]}"
}

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
    echo "  DRAMATIQ = (CC_TRAINING: P-$DRAMATIQ_PROCESSES T-$DRAMATIQ_THREADS, GRAPH: P-1 T-$DRAMATIQ_THREADS_GRAPH)"
    # echo "  DRAMATIQ = (CC_TRAINING: P-$DRAMATIQ_PROCESSES T-$DRAMATIQ_THREADS, GRAPH: P-1 T-$DRAMATIQ_THREADS_GRAPH, SVG2PNG: P-1 T-1)"

    parse_supervisor_config "$CONFIG"
}

check_process_status() {
    local max_attempts=30
    local check_interval=2
    local attempt=0
    
    echo "🔍 检查进程启动状态..."
    
    # 确保已解析配置文件
    if [ ${#SUPERVISOR_PROGRAMS[@]} -eq 0 ]; then
        parse_supervisor_config "$CONFIG"
    fi
    
    while [ $attempt -lt $max_attempts ]; do
        # 获取当前状态
        local status_output=$(supervisorctl -c "$CONFIG" status 2>/dev/null)
        
        if [ $? -ne 0 ]; then
            echo "❌ 无法连接到supervisor，可能未正确启动"
            return 1
        fi
        
        # 动态检查所有程序状态
        local all_running=true
        local all_status=""
        local failed_programs=()
        local starting_programs=()
        
        for program in "${SUPERVISOR_PROGRAMS[@]}"; do
            local program_status=$(echo "$status_output" | grep "^$program" | awk '{print $2}')
            all_status="$all_status $program:$program_status"
            
            if [[ "$program_status" != "RUNNING" ]]; then
                all_running=false
                
                if [[ "$program_status" == "FATAL" ]]; then
                    failed_programs+=("$program")
                elif [[ "$program_status" == "STARTING" ]]; then
                    starting_programs+=("$program")
                fi
            fi
        done
        
        echo "  [$((attempt+1))/$max_attempts]$all_status"
        
        # 如果所有进程都在运行，则成功
        if $all_running; then
            echo "✅ 所有进程启动成功！"
            echo "📊 当前状态:"
            supervisorctl -c "$CONFIG" status
            return 0
        fi
        
        # 检查是否有进程启动失败
        if [ ${#failed_programs[@]} -gt 0 ]; then
            echo "❌ 发现进程启动失败: ${failed_programs[*]}"
            echo "📊 详细状态:"
            supervisorctl -c "$CONFIG" status
            show_startup_errors
            return 1
        fi
        
        # 如果还在启动中，继续等待
        if [ ${#starting_programs[@]} -gt 0 ]; then
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
    
    # 动态生成日志建议
    if [ ${#FLASK_PROGRAMS[@]} -gt 0 ]; then
        echo "2. 查看Flask应用日志:"
        for program in "${FLASK_PROGRAMS[@]}"; do
            if [[ -n "${PROGRAM_ERR_LOGS[$program]}" ]]; then
                echo "   tail -f ${PROGRAM_ERR_LOGS[$program]}"
            fi
            if [[ -n "${PROGRAM_OUT_LOGS[$program]}" ]]; then
                echo "   tail -f ${PROGRAM_OUT_LOGS[$program]}"
            fi
        done
        echo ""
    fi
    
    if [ ${#DRAMATIQ_PROGRAMS[@]} -gt 0 ]; then
        echo "3. 查看Dramatiq任务队列日志:"
        for program in "${DRAMATIQ_PROGRAMS[@]}"; do
            if [[ -n "${PROGRAM_ERR_LOGS[$program]}" ]]; then
                echo "   tail -f ${PROGRAM_ERR_LOGS[$program]}"
            fi
            if [[ -n "${PROGRAM_OUT_LOGS[$program]}" ]]; then
                echo "   tail -f ${PROGRAM_OUT_LOGS[$program]}"
            fi
        done
        echo ""
    fi
    
    echo "4. 检查端口占用情况:"
    echo "   lsof -i :$(echo $GUNICORN_ADDRESS | cut -d':' -f2)"
    echo ""
    echo "5. 检查Python环境和依赖:"
    echo "   which python"
    echo "   pip list | grep -E '(flask|gunicorn|dramatiq)'"
    echo ""
    echo "6. 手动测试启动命令:"
    for program in "${SUPERVISOR_PROGRAMS[@]}"; do
        if [[ -n "${PROGRAM_COMMANDS[$program]}" ]]; then
            echo "   # $program"
            echo "   ${PROGRAM_COMMANDS[$program]}"
        fi
    done
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
        
        # 确保已解析配置文件
        if [ ${#SUPERVISOR_PROGRAMS[@]} -eq 0 ]; then
            parse_supervisor_config "$CONFIG"
        fi
        
        # 先停止 dramatiq worker
        if [ ${#DRAMATIQ_PROGRAMS[@]} -gt 0 ]; then
            echo "⏳ 正在停止所有 dramatiq worker..."
            if ! supervisorctl -c "$CONFIG" stop "${DRAMATIQ_PROGRAMS[@]}"; then
                echo "❌ 停止 dramatiq worker 失败"
                exit 1
            fi
            
            # 等待 dramatiq 任务完成
            echo "⏳ 等待 dramatiq 任务完成..."
            echo "请等待执行中的任务完成，预计最多需要几分钟，强行停止可能导致任务和成绩异常..."
            while true; do
                if ! pgrep -f "dramatiq" > /dev/null; then
                    break
                fi
                sleep 1
            done
            echo "✅ 所有 dramatiq worker 已停止"
        fi
        
        # 然后停止 flask 应用
        if [ ${#FLASK_PROGRAMS[@]} -gt 0 ]; then
            echo "⏳ 正在停止 flask 应用..."
            if ! supervisorctl -c "$CONFIG" stop "${FLASK_PROGRAMS[@]}"; then
                echo "❌ 停止 flask 应用失败"
                exit 1
            fi
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
        pgrep -f "dramatiq.*app_backend" -l 2>/dev/null || echo "    未找到dramatiq进程"
        
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
        
        # 确保已解析配置文件
        if [ ${#SUPERVISOR_PROGRAMS[@]} -eq 0 ]; then
            parse_supervisor_config "$CONFIG"
        fi
        
        echo "📋 查看日志文件..."
        echo "请选择要查看的日志:"
        
        menu_index=1
        declare -a log_options
        
        # 添加supervisor主日志
        echo "$menu_index) Supervisor主日志"
        log_options[$menu_index]="$LOG_DIR/supervisord.log"
        menu_index=$((menu_index + 1))
        
        # 添加app日志
        echo "$menu_index) App日志"
        log_options[$menu_index]="$LOG_DIR/app.log"
        menu_index=$((menu_index + 1))
        
        # 动态添加所有程序的日志选项
        for program in "${SUPERVISOR_PROGRAMS[@]}"; do
            if [[ -n "${PROGRAM_ERR_LOGS[$program]}" ]]; then
                echo "$menu_index) ${program}错误日志"
                log_options[$menu_index]="${PROGRAM_ERR_LOGS[$program]}"
                menu_index=$((menu_index + 1))
            fi
            
            if [[ -n "${PROGRAM_OUT_LOGS[$program]}" ]]; then
                echo "$menu_index) ${program}输出日志"
                log_options[$menu_index]="${PROGRAM_OUT_LOGS[$program]}"
                menu_index=$((menu_index + 1))
            fi
        done
        
        # 添加Flask access日志（如果有Flask程序）
        if [ ${#FLASK_PROGRAMS[@]} -gt 0 ]; then
            for program in "${FLASK_PROGRAMS[@]}"; do
                if [[ -n "${PROGRAM_ACCESS_LOGS[$program]}" ]]; then
                    echo "$menu_index) ${program} access日志"
                    log_options[$menu_index]="${PROGRAM_ACCESS_LOGS[$program]}"
                    menu_index=$((menu_index + 1))
                fi
            done
        fi
        
        # 添加查看所有错误日志选项
        echo "$menu_index) 查看所有最新错误日志"
        log_options[$menu_index]="all_errors"
        
        read -p "请选择 (1-$menu_index): " choice
        
        if [ "$choice" -ge 1 ] && [ "$choice" -le "$menu_index" ]; then
            if [ "${log_options[$choice]}" = "all_errors" ]; then
                echo "显示所有错误日志的最后20行:"
                echo "=== Supervisor主日志 ==="
                tail -20 "$LOG_DIR/supervisord.log" 2>/dev/null || echo "日志文件不存在"
                echo ""
                
                for program in "${SUPERVISOR_PROGRAMS[@]}"; do
                    if [[ -n "${PROGRAM_ERR_LOGS[$program]}" ]]; then
                        echo "=== ${program}错误日志 ==="
                        tail -20 "${PROGRAM_ERR_LOGS[$program]}" 2>/dev/null || echo "日志文件不存在"
                        echo ""
                    fi
                done
            else
                echo "正在查看日志: ${log_options[$choice]}"
                echo "按 Ctrl+C 退出日志查看"
                tail -f "${log_options[$choice]}"
            fi
        else
            echo "❌ 无效选择"
        fi
        ;;
    *)
        echo "使用方法: $0 {start|stop|status|restart|config|logs}"
        exit 1
esac
