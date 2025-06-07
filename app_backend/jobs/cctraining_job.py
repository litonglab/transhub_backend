import logging
import os
import subprocess
import traceback
import uuid

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import TimeLimit
from redis.lock import Lock

from app_backend import db, redis_client, get_default_config
from app_backend import get_app
from app_backend.model.Rank_model import Rank_model
from app_backend.model.Task_model import Task_model
from app_backend.model.User_model import User_model
from app_backend.model.graph_model import graph_model
from app_backend.utils.utils import get_available_port, release_port, setup_logger

# 设置日志记录器
setup_logger()
logger = logging.getLogger(__name__)
config = get_default_config()
redis_broker = RedisBroker(url=config.Cache.FLASK_REDIS_URL)
redis_broker.add_middleware(TimeLimit())
dramatiq.set_broker(redis_broker)


# 待续

@dramatiq.actor(time_limit=1200000, max_retries=0)
def run_cc_training_task(task_id):
    app = get_app()
    with app.app_context():
        log_path = None
        try:
            db.session.expire_all()  # 刷新会话
            task = Task_model.query.filter_by(task_id=task_id).first()
            if not task:
                logger.error(f"Task {task_id} not found")
                return

            parent_dir = os.path.dirname(task.task_dir)
            log_path = f"{parent_dir}/run.log"

            logger.info(f"Start task {task_id}")
            user = User_model.query.filter_by(user_id=task.user_id).first()
            lock_name = user.user_id
            lock = Lock(redis_client, lock_name, timeout=600)
            with lock:
                # 如果上锁就等待
                # 1. 将用户目录下的文件拷贝到用户目录对应的cc-training目录下
                task.update(task_status='compling')
                cc_training_dir = user.get_competition_project_dir(task.cname)
                target_dir = cc_training_dir + "/datagrump"
                logger.info(f"cc_training_dir: {cc_training_dir}, target_dir: {target_dir}")
                if not os.path.exists(target_dir):
                    # 抛出异常，调用job_failure_call_back
                    logger.error(f"cc-training dir not found: {target_dir}")
                    task.update(task_status='error')
                    return
                # 拷贝文件
                # 删除target_dir中的名为 controller.cc 的文件
                if os.path.exists(target_dir + "/controller.cc"):
                    os.remove(target_dir + "/controller.cc")
                    logger.info(f"Removed old controller.cc")
                parent_dir = os.path.dirname(task.task_dir)
                if not os.path.exists(task.task_dir):
                    os.mkdir(task.task_dir)
                    logger.info(f"Created task dir: {task.task_dir}")
                # 将用户上传的文件拷贝到target_dir中，并直接命名为 controller.cc，避免覆盖
                if not run_cmd(f'cp {parent_dir}/{task.algorithm}.cc {target_dir}/controller.cc',
                               f'{task.task_dir}/error.log', task):
                    logger.error(f"cp failed: {parent_dir}/{task.algorithm}.cc -> {target_dir}")
                    task.update(task_status='error')
                    return
                # 2. 编译并创建trace文件夹
                if not run_cmd(f'cd {target_dir} && make clean && make', f'{task.task_dir}/error.log', task):
                    logger.error(f"make failed in {target_dir}")
                    task.update(task_status='error')
                    return
                # 先在task.task_dir中创建对应的trace文件夹，再将targetdir下的sender,receiver拷贝到trace文件夹中
                trace_dir = task.task_dir
                if not run_cmd(
                        f'mkdir -p {trace_dir} && cp {target_dir}/sender {trace_dir} && cp {target_dir}/receiver {trace_dir}',
                        f'{task.task_dir}/error.log', task):
                    logger.error(f"copy sender/receiver failed to {trace_dir}")
                    task.update(task_status='error')
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
                running_port = get_available_port(redis_client)
                logger.info(f"select port {running_port} for running {task.task_id}")
                task.update(task_status='running')
                _config = config.Course.ALL_CLASS[task.cname]
                loss_rate = task.loss_rate
                uplink_dir = _config['uplink_dir']
                downlink_dir = _config['downlink_dir']
                # 遍历所有的trace文件，执行
                uplink_file = uplink_dir + "/" + task.trace_name + ".up"
                downlink_file = downlink_dir + "/" + task.trace_name + ".down"
                result_path = task.task_dir + "/" + task.trace_name + ".log"
                sender_path = task.task_dir + "/sender"
                receiver_path = task.task_dir + "/receiver"
                # os.system( f'cd {target_dir} && {program_script} {running_port} {loss_rate} {uplink_file} {
                # downlink_file} {result_path}')
                retry_limit = 10
                retry_time = 0
                while not run_cmd(
                        f"cd {target_dir} && {program_script} {running_port} {loss_rate} {uplink_file} {downlink_file} {result_path} {sender_path} {receiver_path} {task.buffer_size}",
                        f'{task.task_dir}/error.log', task) and retry_time < retry_limit:
                    retry_time += 1
                    logger.error(f"run-contest.sh failed, retry {retry_time}/{retry_limit}")
                    task.update(task_status='retrying')
                if retry_time == retry_limit:
                    logger.error(f"run-contest.sh failed after {retry_limit} retries")
                    task.update(task_status='error')
                    return
                # 4. 解析结果
                extract_program = "mm-throughput-graph"
                if not run_cmd(
                        f'{extract_program} 500 {result_path} 2> {task.task_dir}/{task.trace_name}.score > /dev/null',
                        f'{task.task_dir}/error.log', task):
                    logger.error(f"mm-throughput-graph failed")
                    task.update(task_status='error')
                    return
                total_score = evaluate_score(task, f'{task.task_dir}/{task.trace_name}.score')
                total_score = round(total_score, 4)
                # 5. 画图
                # tunnel_graph = TunnelGraph(
                #     tunnel_log=result_path,
                #     throughput_graph=task.task_dir + "/" + task.trace_name + ".throughput.png",
                #     delay_graph=task.task_dir + "/" + task.trace_name + ".delay.png",
                #     ms_per_bin=500)
                # tunnel_graph.run()
                if not run_cmd(
                        f'mm-throughput-graph 500 {result_path} > ' + task.task_dir + "/" + task.trace_name + ".throughput.svg",
                        f'{task.task_dir}/error.log', task):
                    logger.error(f"throughput graph failed")
                    task.update(task_status='error')
                    return
                if not run_cmd(
                        f'mm-delay-graph {result_path} > ' + task.task_dir + "/" + task.trace_name + ".delay.svg",
                        f'{task.task_dir}/error.log', task):
                    logger.error(f"delay graph failed")
                    task.update(task_status='error')
                    return
                # 6. 保存图
                graph_id1 = uuid.uuid4().hex
                graph_id2 = uuid.uuid4().hex
                graph_model(task_id=task_id, graph_id=str(graph_id1), graph_type='throughput',
                            graph_path=task.task_dir + "/" + task.trace_name + ".throughput.svg").insert()
                graph_model(task_id=task_id, graph_id=str(graph_id2), graph_type='delay',
                            graph_path=task.task_dir + "/" + task.trace_name + ".delay.svg").insert()
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
                        rank_record.update(task_score=total_score + rank_record.task_score)
                        logger.info(f"Updated existing rank record: {rank_record.upload_id}")
                    else:
                        # Step 2: Record exists, update it
                        rank_record.update(upload_id=task.upload_id, task_score=total_score, algorithm=task.algorithm,
                                           upload_time=task.created_time)
                        logger.info(f"Updated rank record with new upload_id: {task.upload_id}")
                else:
                    # Step 3: Record does not exist, create and add it
                    Rank_model(user_id=task.user_id, upload_id=task.upload_id, task_score=total_score,
                               algorithm=task.algorithm, upload_time=task.created_time, cname=task.cname,
                               username=user.username).insert()
                    logger.info(f"Created new rank record for user: {task.user_id}")
                logger.info(f"task {task_id} finished, score: {total_score}")
            except Exception as e:
                err_msg = str(e)
                tb = traceback.format_exc()
                with open(f'{task.task_dir}/error.log', 'w') as f:
                    f.write(err_msg + "\n" + tb)
                logger.error(f"Exception in inner try: {err_msg}\n{tb}", level="error")
                task.update(task_status='error')
        except Exception as e:
            # 兜底异常
            err_msg = str(e)
            tb = traceback.format_exc()
            if log_path:
                with open(log_path, 'a') as logf:
                    logf.write(f"[FATAL] Exception in outer try: {err_msg}\n{tb}\n")
            else:
                with open('run.log', 'a') as logf:
                    logf.write(f"[FATAL] Exception before task_dir: {err_msg}\n{tb}\n")
            if 'task' in locals() and task:
                task.update(task_status='error')
        finally:
            try:
                release_port(locals().get('running_port', None), redis_client)
            except Exception as e:
                if log_path:
                    with open(log_path, 'a') as logf:
                        logf.write(f"[WARN] Exception in release_port: {e}\n")
            try:
                db.session.remove()
            except Exception as e:
                if log_path:
                    with open(log_path, 'a') as logf:
                        logf.write(f"[WARN] Exception in db.session.remove: {e}\n")


def run_cmd(cmd, error_file, task):
    logger.info(f"Running command for task {task.task_id}: {cmd}")
    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    with open(error_file, 'a') as f:
        f.write(cmd)
        f.write(result.stdout.decode('utf-8'))
        f.write(result.stderr.decode('utf-8'))
        f.write('\n\n')
    if result.returncode != 0:
        logger.error(f"Command failed for task {task.task_id} with return code {result.returncode}")
        logger.error(f"Command output: {result.stdout.decode('utf-8')}")
        logger.error(f"Command error: {result.stderr.decode('utf-8')}")
        task.update(task_status='error')
        # 将错误信息写入task_dir/error.log
        return False
    logger.debug(f"Command completed successfully for task {task.task_id}")
    return True


def enqueue_cc_task(task_id):
    """
    将任务发送到队列

    Args:
        task_id (str): 任务ID

    Returns:
        dict: 包含发送状态的字典
        {
            'success': bool,
            'message': str,
            'message_id': str or None,
            'task_id': str
        }
    """
    logger.info(f"Enqueueing task {task_id}")
    try:
        # 发送任务到队列
        message = run_cc_training_task.send(task_id)

        # 检查消息是否成功创建
        if message and hasattr(message, 'message_id'):
            logger.info(f"Task {task_id} successfully enqueued with message ID: {message.message_id}")
            return {
                'success': True,
                'message': 'Task successfully enqueued',
                'message_id': message.message_id,
                'task_id': task_id
            }
        else:
            logger.error(f"Failed to enqueue task {task_id}: No message ID returned")
            return {
                'success': False,
                'message': 'Failed to enqueue task: No message ID returned',
                'message_id': None,
                'task_id': task_id
            }

    except Exception as e:
        logger.error(f"Failed to enqueue task {task_id}: {str(e)}", exc_info=True)
        return {
            'success': False,
            'message': str(e),
            'message_id': None,
            'task_id': task_id
        }


def enqueue_multiple_tasks(task_ids):
    """
    批量发送多个任务到队列

    Args:
        task_ids (list): 任务ID列表

    Returns:
        dict: 批量入队结果
        {
            'success': bool,
            'total_tasks': int,
            'successful_enqueues': int,
            'failed_enqueues': int,
            'results': list,
            'failed_tasks': list
        }
    """
    logger.info(f"Enqueueing multiple tasks: {task_ids}")
    results = []
    failed_tasks = []

    for task_id in task_ids:
        result = enqueue_cc_task(task_id)
        results.append(result)

        if not result['success']:
            failed_tasks.append({
                'task_id': task_id,
                'error': result['message']
            })

    successful_enqueues = sum(1 for result in results if result['success'])
    total_tasks = len(task_ids)
    logger.info(f"Enqueued {len(task_ids)} tasks, {sum(1 for r in results if r['success'])} successful")

    return {
        'success': len(failed_tasks) == 0,
        'total_tasks': total_tasks,
        'successful_enqueues': successful_enqueues,
        'failed_enqueues': len(failed_tasks),
        'results': results,
        'failed_tasks': failed_tasks
    }


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
