
# ./run-contest.sh 12345 0.01 /mnt/f/Linux/project/Transhub_data/pantheon-network/test_data/Verizon-LTE-short.up /mnt/f/Linux/project/Transhub_data/pantheon-network/test_data/Verizon-LTE-short.down ./result.log


#!/bin/bash

if [ $# -ne 5 ]; then
    echo "Usage: $0 running_port loss_rate uplink_file downlink_file result_path"
    exit 1
fi

running_port=$1
loss_rate=$2
uplink_file=$3
downlink_file=$4
result_path=$5

# Start receiver in background
./receiver $running_port &
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
command="mm-delay 20 mm-loss uplink $loss_rate mm-link $downlink_file $uplink_file --once --uplink-log=$result_path -- bash -c './sender \$MAHIMAHI_BASE $running_port'"

# Run the command in background
echo "Executing command: $command"
eval $command &

# Wait for the command to finish
wait $!

# Kill the receiver
kill -9 $receiver_pid

echo
echo " done."
echo
