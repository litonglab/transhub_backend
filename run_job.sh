#!/bin/bash -e
# input: cca_name, running_port, task_id
TARGET_DIR=/home/liuwei/Transhub_data/cc_training/$3
RESULT_DIR=$TARGET_DIR/sourdough/datagrump/result
LOG_DIR=/home/liuwei/Transhub_data/cc_training/log
SUMMARY_DIR="$4"

# execute sql to finish job and update score
mysql -uroot -pLitonglablw_1 -e "
use transhub_base;
update task set cca_name='$1', running_port=$2, task_status='running' where task_id ='$3';
" >> /dev/null

if [ ! -d "$TARGET_DIR" ]; then
	mkdir -p $TARGET_DIR
fi
cp -r ~/sourdough $TARGET_DIR
cp /home/liuwei/Transhub_data/received/$1.cc $TARGET_DIR/sourdough/datagrump/controller.cc
cd $TARGET_DIR/sourdough/datagrump
make
temp_status=$?
echo "tempresult is $temp_status" 
if [ "$temp_status" -ne "0" ]; then
	# execute sql to finish job and update score
	mysql -uroot -pLitonglablw_1 -e "
	use transhub_base;
	update task set task_status='COMPILE ERROR' where task_id ='$3';
	" >> /dev/null
fi
mkdir -p $RESULT_DIR
echo 250250 | sudo -S sysctl -w net.ipv4.ip_forward=1
timeout -s INT 20m ./run-contest "$1" "$2"
nohup ./mm-throughput-stat 500 ./contest_uplink_log | tee nohup.out
cp $LOG_DIR/$3_logfile.txt $RESULT_DIR/$3_throughput.txt
average_capacity=$(grep 'Average capacity' $RESULT_DIR/$3_throughput.txt | awk '{print$3}')
average_throughput=$(grep -m 1 'Average throughput' $RESULT_DIR/$3_throughput.txt | awk '{print$3}')
queue_delay=$(grep -m 1 '95th percentile per-packet' $RESULT_DIR/$3_throughput.txt | awk '{printf"%.5f\n", $6/1000}')
signal_delay=$(grep -m 1 '95th percentile signal' $RESULT_DIR/$3_throughput.txt | awk '{print$5}')
echo $average_throughput
echo $signal_delay
score=$(echo "l($average_throughput/$signal_delay)+5" | bc -l)
timeout -s INT 20m ./run-contest-loss-trace "$1" "$2"
nohup ./mm-throughput-stat 500 ./contest_uplink_loss_log | tee nohup.out
echo "output another trace result"
mv $LOG_DIR/$3_logfile.txt $RESULT_DIR/$3_throughput.txt
average_capacity_loss=$(grep 'Average capacity' $RESULT_DIR/$3_throughput.txt | awk '{print$3}')
average_throughput_loss=$(grep -m 2 'Average throughput' $RESULT_DIR/$3_throughput.txt | tail -n 1 | awk '{print$3}')
queue_delay_loss=$(grep -m 2 '95th percentile per-packet' $RESULT_DIR/$3_throughput.txt | tail -n 1 | awk '{printf"%.5f\n", $6/1000}')
signal_delay_loss=$(grep -m 2 '95th percentile signal' $RESULT_DIR/$3_throughput.txt | tail -n 1 | awk '{print$5}')
echo $average_throughput_loss
echo $signal_delay_loss
score_loss=$(echo "l($average_throughput_loss/$signal_delay_loss)+5" | bc -l)

echo $score >> $RESULT_DIR/$3_score.txt
echo $score_loss >> $RESULT_DIR/$3_score.txt
half_score=$(echo "scale=2; $score / 2" | bc)
half_score_loss=$(echo "scale=2; $score_loss / 2" | bc)
final_score=$(echo "$half_score_loss + $half_score" | bc)
# execute sql to finish job and update score
mysql -uroot -pLitonglablw_1 -e "
use transhub_base;
update task set task_score=$final_score, score_without_loss=$score, score_with_loss=$score_loss, task_status='finished' where task_id ='$3';
" >> $RESULT_DIR/$3_throughput.txt

mv controller.cc $RESULT_DIR/$1.cc
cp ./contest_uplink_log $RESULT_DIR/contest_uplink_log
cp ./contest_uplink_loss_log $RESULT_DIR/contest_uplink_loss_log
python $SUMMARY_DIR/src/analysis/tunnel_graph.py --throughput $RESULT_DIR/throughput.png --delay $RESULT_DIR/delay.png $RESULT_DIR/contest_uplink_log
python $SUMMARY_DIR/src/analysis/tunnel_graph.py --throughput $RESULT_DIR/throughput_loss_trace.png --delay $RESULT_DIR/delay_loss_trace.png $RESULT_DIR/contest_uplink_loss_log

sudo cp ./contest_uplink_log $SUMMARY_DIR/src/experiments/data/$1_datalink_run1.log
sudo cp ./contest_uplink_loss_log $SUMMARY_DIR/src/experiments/data_p/$1_datalink_run1.log
cd $SUMMARY_DIR/src/analysis
#python $SUMMARY_DIR/src/analysis/plot.py
#cp $SUMMARY_DIR/src/experiments/data/pantheon_summary.* $RESULT_DIR
#cp $SUMMARY_DIR/src/experiments/data_p/pantheon_summary.pdf $RESULT_DIR/panthon_summary_loss.pdf


