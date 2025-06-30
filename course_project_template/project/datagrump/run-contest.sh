#!/bin/bash
# run-contest.sh 专用于transhub后端，区分于原项目使用的 run-contest
# 主要改变：增加了参数；在评测运行错误时exit1，以便更新任务状态为error，不计算分数；并保证脚本退出时关闭所有进程
# 忽略sender的输出，避免输出用户代码里打印的过多信息

if [ $# -ne 8 ]; then
    echo [$(date "+%Y-%m-%d %H:%M:%S")] "Usage: $0 running_port loss_rate uplink_file downlink_file result_path sender_path receiver_path buffer_size"
    exit 1
fi

running_port=$1
loss_rate=$2
uplink_file=$3
downlink_file=$4
result_path=$5
sender_path=$6
receiver_path=$7
buffer_size=$8

start_time=$(date +%s)

cleanup() {
    # 终止 command 进程
    if [ -n "$command_pid" ] && ps -p "$command_pid" > /dev/null; then
        echo [$(date "+%Y-%m-%d %H:%M:%S")] "Terminating command process (PID: $command_pid)..."
        kill -9 "$command_pid" 2>/dev/null
    fi

    # 终止 receiver 进程
    if [ -n "$receiver_pid" ] && ps -p "$receiver_pid" > /dev/null; then
        echo [$(date "+%Y-%m-%d %H:%M:%S")] "Terminating receiver process (PID: $receiver_pid)..."
        kill -9 "$receiver_pid" 2>/dev/null
    fi
    echo [$(date "+%Y-%m-%d %H:%M:%S")] "Cleanup completed."
}
trap cleanup EXIT INT TERM

# Start receiver in background
echo [$(date "+%Y-%m-%d %H:%M:%S")] "Starting receiver..."
$receiver_path $running_port &
receiver_pid=$!

if [ -z "$receiver_pid" ]; then
    echo [$(date "+%Y-%m-%d %H:%M:%S")] "Failed to start receiver"
    exit 1
fi

# Wait for a short moment to ensure receiver starts properly
sleep 2

# 检查 receiver 是否正常启动
if ! ps -p "$receiver_pid" > /dev/null; then
    echo [$(date "+%Y-%m-%d %H:%M:%S")] "Receiver process failed to start (PID: $receiver_pid). Check for port conflicts or other errors."
    exit 1
fi

prefix=$(dirname $(which mm-link))
tracedir="$prefix/../share/mahimahi/traces"

# Construct the command
# Ignore the output of the sender command, redirect it to /dev/null
command="mm-delay 20 mm-loss uplink $loss_rate mm-link $downlink_file $uplink_file --uplink-queue=droptail --uplink-queue-args=\\\"packets=$buffer_size\\\" --once --uplink-log=$result_path -- bash -c '$sender_path \$MAHIMAHI_BASE $running_port > /dev/null 2>&1'"

# Run the command in background
echo [$(date "+%Y-%m-%d %H:%M:%S")] "starting sender..."

# debug only: 打印实际执行的命令，仅用于调试，现网环境保持注释，不展示给用户
# echo [$(date "+%Y-%m-%d %H:%M:%S")] "Executing sender command: $command"


echo [$(date "+%Y-%m-%d %H:%M:%S")] "running contest..."
eval $command &
command_pid=$!

if [ $? -ne 0 ]; then
    echo [$(date "+%Y-%m-%d %H:%M:%S")] "Error: Command execution failed"
    exit 1
fi

# Wait for the command to finish
wait $command_pid
if [ $? -ne 0 ]; then
    echo [$(date "+%Y-%m-%d %H:%M:%S")] "Error: Command exited with non-zero status"
    exit 1
fi

# sender 结束后，判断 receiver 是否还存活，如果不存活说明receiver提前退出了
if ! ps -p "$receiver_pid" > /dev/null; then
    echo [$(date "+%Y-%m-%d %H:%M:%S")] "Error: Receiver process (PID: $receiver_pid) exited before sender finished."
    exit 1
fi

# 不再手动 kill receiver，交给 trap/cleanup 统一处理

end_time=$(date +%s)
elapsed=$((end_time - start_time))
echo [$(date "+%Y-%m-%d %H:%M:%S")] "run contest done. Total time: ${elapsed}s."
