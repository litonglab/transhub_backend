import os
import uuid
from redis import Redis
from redis.lock import Lock
from app_backend import db
from app_backend.model.Task_model import Task_model
from app_backend.model.User_model import User_model
from app_backend.model.Rank_model import Rank_model
from app_backend.model.graph_model import graph_model
from app_backend.analysis.tunnel_graph import TunnelGraph
from app_backend.utils import get_available_port, release_port
from app_backend.config import get_config_by_cname
from app_backend import get_app
import subprocess

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import TimeLimit

redis_broker = RedisBroker(url="redis://localhost:6379/0")
redis_broker.add_middleware(TimeLimit())
redis_client = Redis(host='localhost', port=6379, db=0)
dramatiq.set_broker(redis_broker)


# 待续

@dramatiq.actor(time_limit=1200000)
def run_cc_training_task(task_id):
    app = get_app()
    with app.app_context():
        print("start task {}".format(task_id))
        db.session.expire_all()  # 刷新会话
        task = Task_model.query.filter_by(task_id=task_id).first()
        if not task:
            print(f"task {task_id} not found")
        # 1. 将用户目录下的文件拷贝到用户目录对应的cc-training目录下
        user = User_model.query.filter_by(user_id=task.user_id).first()
        lock_name = user.user_id
        lock = Lock(redis_client, lock_name, timeout=600)
        with lock:
            # 如果上锁就等待
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
            parent_dir = os.path.dirname(task.task_dir)
            if not os.path.exists(task.task_dir):
                os.mkdir(task.task_dir)
            #os.system(f'cp {parent_dir}/{task.algorithm}.cc {target_dir}')
            if not run_cmd(f'cp {parent_dir}/{task.algorithm}.cc {target_dir}', f'{task.task_dir}/error.log', task):
                return
            # 重命名
           # os.system(f'mv {parent_dir}/{task.algorithm}.cc {target_dir}/controller.cc')
            if not run_cmd(f'mv {target_dir}/{task.algorithm}.cc {target_dir}/controller.cc', f'{task.task_dir}/error.log', task):
                return

            # 2. 编译并创建trace文件夹
            if not run_cmd(f'cd {target_dir} && make clean && make', f'{task.task_dir}/error.log', task):
                return
            # 先在task.task_dir中创建对应的trace文件夹，再将targetdir下的sender,receiver拷贝到trace文件夹中
            trace_dir = task.task_dir
            if not run_cmd(
                    f'mkdir -p {trace_dir} && cp {target_dir}/sender {trace_dir} && cp {target_dir}/receiver {trace_dir}',
                    f'{task.task_dir}/error.log', task):
                return

        try:
            # 3. 执行
            program_script = "./run-contest.sh"
            # 该脚本接收五个参数，running_port loss_rate uplink_file downlink_file result_path
            # running_port: 运行端口
            # loss_rate: 丢包率
            # uplink_file: 上行文件
            # downlink_file: 下行文件
            # result_path: 结果路径

            running_port = get_available_port()
            print("select port {} for running {}".format(running_port, task.task_id))
            task.update(task_status='running')
            config = get_config_by_cname(task.cname)
            loss_rate = task.loss_rate
            uplink_dir = config.uplink_dir
            downlink_dir = config.downlink_dir

            # 遍历所有的trace文件，执行
            uplink_file = uplink_dir + "/" + task.trace_name + ".up"
            downlink_file = downlink_dir + "/" + task.trace_name + ".down"
            result_path = task.task_dir + "/" + task.trace_name + ".log"
            sender_path = task.task_dir + "/sender"
            receiver_path = task.task_dir + "/receiver"
            # os.system( f'cd {target_dir} && {program_script} {running_port} {loss_rate} {uplink_file} {
            # downlink_file} {result_path}')
            retry_limit = 10
            retry_times = 0
            while not run_cmd(
                    f"cd {target_dir} && {program_script} {running_port} {loss_rate} {uplink_file} {downlink_file} {result_path} {sender_path} {receiver_path} {task.buffer_size}",
                    f'{task.task_dir}/error.log', task) and retry_time < retry_limit:
                retry_time+=1
                task.update(task_status='retrying')
            if retry_times == retry_limit:
                task.update(task_status='error')
                return
            # 4. 解析结果
            extract_program = "mm-throughput-stat"

            if not run_cmd(
                    f'{target_dir}/{extract_program} 500 {result_path} > {task.task_dir}/{task.trace_name}.score',
                    f'{task.task_dir}/error.log', task):
                return
            total_score = evaluate_score(task, f'{task.task_dir}/{task.trace_name}.score')

            # 5. 画图
            tunnel_graph = TunnelGraph(
                tunnel_log=result_path,
                throughput_graph=task.task_dir + "/" + task.trace_name + ".throughput.png",
                delay_graph=task.task_dir + "/" + task.trace_name + ".delay.png",
                ms_per_bin=500)
            tunnel_graph.run()
            # 6. 保存图
            graph_id1 = uuid.uuid4().hex
            graph_id2 = uuid.uuid4().hex
            graph_model(task_id=task_id, graph_id=str(graph_id1), graph_type='throughput',
                        graph_path=task.task_dir + "/" + task.trace_name + ".throughput.png").insert()
            graph_model(task_id=task_id, graph_id=str(graph_id2), graph_type='delay',
                        graph_path=task.task_dir + "/" + task.trace_name + ".delay.png").insert()

            # uplink_file = cctraining_config.uplink_file
            # downlink_file = cctraining_config.downlink_file
            #
            # result_path = task.task_dir + "/result.log" os.system( f'cd {target_dir} && {program_script} {
            # running_port} {loss_rate} {uplink_file} {downlink_file} {result_path}') 解锁

            # 成功后的回调
            task.update(task_status='finished', task_score=total_score)
            # Step 1: Try to retrieve the Rank_model record
            rank_record = Rank_model.query.get(task.user_id)
            if rank_record:
                if rank_record.upload_id == task.upload_id:
                    rank_record.update(task_score=total_score+rank_record.task_score)
                # Step 2: Record exists, update it
                rank_record.update(upload_id=task.upload_id, task_score=total_score, algorithm=task.algorithm,
                                   upload_time=task.created_time)
            else:
                # Step 3: Record does not exist, create and add it
                Rank_model(user_id=task.user_id, upload_id=task.upload_id, task_score=total_score, algorithm=task.algorithm,
                           upload_time=task.created_time,cname = task.cname,user_name = user.username).insert()
            print("task {} finished".format(task_id))
        except Exception as e:
            # 失败后的回调
            # print(f"run_cc_training_task error: {e}")
            with open(f'{task.task_dir}/error.log', 'w') as f:
                f.write(str(e))
            task.update(task_status='error')
        finally:
            # 释放端口
            release_port(running_port)


def run_cmd(cmd, error_file, task):
    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    with open(error_file, 'a') as f:
        f.write(cmd)
        f.write(result.stdout.decode('utf-8'))
        f.write(result.stderr.decode('utf-8'))
        f.write('\n\n')
    if result.returncode != 0:
        task.update(task_status='error')
        # 将错误信息写入task_dir/error.log
        return False
    return True


def enqueue_cc_task(task_id):
    run_cc_training_task.send(task_id)


def evaluate_score(task: Task_model, score_file: str):
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
