#!/bin/bash
# run-contest.sh 专用于transhub后端，原项目使用的run-contest.sh已备份为run-contest-bak.sh
# 主要改变：增加了参数；在评测运行错误时exit1，以便更新任务状态为error，不计算分数

if [ $# -ne 8 ]; then
    echo "Usage: $0 running_port loss_rate uplink_file downlink_file result_path sender_path receiver_path buffer_size"
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
# Start receiver in background
$receiver_path $running_port &
receiver_pid=$!

if [ -z "$receiver_pid" ]; then
    echo "Failed to start receiver"
    exit 1
fi

# Wait for a short moment to ensure receiver starts properly
sleep 1

prefix=$(dirname $(which mm-link))
tracedir="$prefix/../share/mahimahi/traces"

# Construct the command
command="mm-delay 20 mm-loss uplink $loss_rate mm-link $downlink_file $uplink_file --uplink-queue=droptail --uplink-queue-args=\\\"packets=$buffer_size\\\" --once --uplink-log=$result_path -- bash -c '$sender_path \$MAHIMAHI_BASE $running_port'"

# Run the command in background
echo "Executing command: $command"
eval $command &
command_pid=$!

if [ $? -ne 0 ]; then
    echo "Error: Command execution failed"
    kill -9 $receiver_pid
    exit 1
fi

# Wait for the command to finish
wait $command_pid
if [ $? -ne 0 ]; then
    echo "Error: Command exited with non-zero status"
    kill -9 $receiver_pid
    exit 1
fi


# Kill the receiver
kill -9 $receiver_pid

echo
echo " run contest done."
echo
