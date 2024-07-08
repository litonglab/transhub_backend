import os

from app.extensions import rq
from app.model.Task_model import Task_model
from app.model.User_model import User_model
from app.utils import get_available_port
from app.config import cctraining_config


# 待续

@rq.job(timeout='300s')
def run_cc_training_task(task: Task_model):
    from run import app
    with app.app_context():
        try:
            # 1. 将用户目录下的文件拷贝到用户目录对应的cc-training目录下
            user = User_model.query.filter_by(user_id=task.user_id).first()
            user.lock()
            cc_training_dir = user.get_competition_project_dir(task.cname)
            target_dir = cc_training_dir + "/datagrump"
            if not os.path.exists(target_dir):
                # 抛出异常，调用job_failure_call_back
                raise Exception("cc-training dir not found")
            # 拷贝文件
            # 删除target_dir中的名为 controller.cc 的文件
            if os.path.exists(target_dir + "/controller.cc"):
                os.remove(target_dir + "/controller.cc")
            # 将用户上传的文件拷贝到target_dir中
            os.system(f'cp {task.task_dir}/{task.algorithm}.cc {target_dir}')
            # 重命名
            os.system(f'mv {target_dir}/{task.algorithm}.cc {target_dir}/controller.cc')

            # 2. 编译
            os.system(f'cd {target_dir} && make clean && make')

            # 3. 运行(目前只支持单个trace文件)
            program_script = "./run-contest.sh"
            # 该脚本接收五个参数，running_port loss_rate uplink_file downlink_file result_path
            # running_port: 运行端口
            # loss_rate: 丢包率
            # uplink_file: 上行文件
            # downlink_file: 下行文件
            # result_path: 结果路径

            running_port = get_available_port()
            print("select port {} for running {}".format(running_port, task.task_id))
            task.update(running_port=running_port, task_status='running')

            loss_rate = cctraining_config.loss_rate
            uplink_file = cctraining_config.uplink_file
            downlink_file = cctraining_config.downlink_file

            result_path = task.task_dir + "/result.log"
            os.system(
                f'cd {target_dir} && {program_script} {running_port} {loss_rate} {uplink_file} {downlink_file} {result_path}')

            # 4. 解析结果
            extract_program = "mm-throughput-stat"
            os.system(f'{target_dir}/{extract_program} 500 {result_path} > {task.task_dir}/score.log')

            # 解锁
            user.unlock()

            # 成功后的回调
            task.update(task_status='finished')
        except Exception as e:
            # 失败后的回调
            user.unlock()
            task.update(task_status='error')
            print(f"run_cc_training_task error: {e}")
            task.update(task_status='error')


def enqueue_cc_task(task: Task_model):
    run_cc_training_task.queue(task)

def evaluate_score(task: Task_model, score_file:str):
    # 评分
    """
    Average capacity: 5.04 Mbits/s
    Average throughput: 3.41 Mbits/s (67.7% utilization)
    95th percentile per-packet queueing delay: 52 ms
    95th percentile signal delay: 116 ms

    :param task:
    :param score_file:
    :return:
    """
    capacity = 0
    throughput = 0
    queueing_delay = 0
    signal_delay = 0
    with open(score_file, 'r') as f:
        lines = f.readlines()
        for line in lines:
            if line.startswith("Average throughput"):
                throughput = float(line.split()[2])
                task.update(score=throughput)
            if line.startswith("Average capacity"):
                capacity = float(line.split()[2])
            if line.startswith("95th percentile per-packet queueing delay"):
                queueing_delay = float(line.split()[5])
            if line.startswith("95th percentile signal delay"):
                signal_delay = float(line.split()[4])

        # 假设评分标准如下：
        # - 吞吐量（越高越好），占比40%
        # - 容量（越高越好），占比30%
        # - 排队延迟（越低越好），占比15%
        # - 信号延迟（越低越好），占比15%

    # 归一化
    max_throughput = capacity  # 假设最大值
    max_queueing_delay = 2000.0  # 假设最大值
    max_signal_delay = 2000.0  # 假设最大值

    # 计算各项评分
    throughput_score = (throughput / max_throughput) * 40
    queueing_delay_score = ((max_queueing_delay - queueing_delay) / max_queueing_delay) * 15
    signal_delay_score = ((max_signal_delay - signal_delay) / max_signal_delay) * 15

    # 总评分
    score = throughput_score + queueing_delay_score + signal_delay_score

    # 更新任务的分数
    task.update(score=score)

    return score