import logging
import os
import shutil
import signal
import subprocess

import cairosvg
import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import TimeLimit
from redis.lock import Lock

from app_backend import db, redis_client, get_default_config
from app_backend import get_app
from app_backend.model.graph_model import GraphModel, GraphType
from app_backend.model.rank_model import RankModel
from app_backend.model.task_model import TaskModel, TaskStatus
from app_backend.model.user_model import UserModel
from app_backend.utils.utils import get_available_port, release_port, setup_logger

# 设置日志记录器
setup_logger()
logger = logging.getLogger(__name__)
config = get_default_config()
redis_broker = RedisBroker(url=config.Cache.FLASK_REDIS_URL)
redis_broker.add_middleware(TimeLimit())
dramatiq.set_broker(redis_broker)


def _compile_cc_file(task, course_project_dir, task_parent_dir, sender_path, receiver_path):
    """
    编译CC文件，在公共目录下编译，编译前对目录上锁。
    由于运行的主要瓶颈在运行评测上，编译一般只需要几秒，所以将编译放在公共目录下，简化代码逻辑，节省空间。
    :param task: Task_model对象
    :return: bool, 是否编译成功
    """
    task_id = task.task_id
    cname = task.cname
    cc_file_name = f'{task.algorithm}.cc'

    # 用户目录锁，防止同一用户同一代码下的多个任务同时读写sender和receiver
    # 添加用户锁是因为task会在不同用户之间交替执行，避免同一用户已有编译好的文件时，仍然需要等待公共目录的锁
    # 因为目录路径太长，upload_id等效，upload_id和目录一一对应
    lock_name = f'task_parent_dir_lock_{task.upload_id}'
    user_lock = Lock(redis_client, lock_name, timeout=300)
    logger.info(
        f'[task: {task_id}] try to find exist sender and receiver in {task_parent_dir}, attempting to acquire user lock: {lock_name}')
    with user_lock:
        # 判断是否已经存在编译好的文件
        if os.path.exists(sender_path) and os.path.exists(receiver_path):
            logger.info(
                f"[task: {task_id}] Sender and receiver already exist in {task_parent_dir}, skipping compilation")
            task.update(task_status=TaskStatus.COMPILED)
            return True

        # 判断父级目录是否存在compile_failed，如果有，说明之前编译失败过，直接返回False
        compile_failed_file = os.path.join(task_parent_dir, 'compile_failed')
        if os.path.exists(compile_failed_file):
            logger.warning(f"[task: {task_id}] Compilation failed previously, skipping compilation")
            task.update(task_status=TaskStatus.ERROR,
                        error_log="本次提交的代码在其他任务中编译失败，此任务不再尝试编译，如需查询编译日志，请查询本次提交下的其他任务。")
            return False

        # 如果没有编译好的文件，开始编译
        lock_name = f'compile_lock_{cname}'
        lock = Lock(redis_client, lock_name, timeout=300)
        logger.info(f'[task: {task_id}] Compiling CC file: {cc_file_name}, attempting to acquire lock: {lock_name}')
        with lock:
            task.update(task_status=TaskStatus.COMPILING)
            logger.info(f"[task: {task_id}] Acquired lock: {lock_name}, starting compilation")
            assert os.path.exists(course_project_dir) and os.path.exists(
                task_parent_dir), "Course project directory or task parent directory does not exist"

            # 将用户上传的文件拷贝到course_project_dir中，并直接覆盖已有的 controller.cc
            logger.info(
                f"[task: {task_id}] Copying files from {task_parent_dir} to {course_project_dir}, starting make with {task.algorithm}.cc")
            shutil.copy(f'{task_parent_dir}/{task.algorithm}.cc', f'{course_project_dir}/controller.cc')
            # 执行make命令
            result, output = run_cmd(f'cd {course_project_dir} && make clean && make', task_id, raise_exception=False)
            if not result:
                logger.error(f"[task: {task_id}] make failed in {course_project_dir}, compilation failed")
                # 如果编译失败，在父级目录创建一个文件，文件名为compile_failed，后续同cc_file的其他trace任务不用再重复编译
                with open(compile_failed_file, 'w') as f:
                    pass
                task.update(task_status=TaskStatus.COMPILED_FAILED, error_log=output)
                return False

            # 编译成功后，将sender和receiver移动到父级目录
            logger.info(f"[task: {task_id}] Moving sender and receiver to parent directory {task_parent_dir}")
            shutil.move(os.path.join(course_project_dir, 'sender'), sender_path)
            shutil.move(os.path.join(course_project_dir, 'receiver'), receiver_path)
            task.update(task_status=TaskStatus.COMPILED)
            logger.info(f"[task: {task.task_id}] Compilation succeeded")
            return True


def _run_contest(task, course_project_dir, sender_path, receiver_path, result_path, running_port):
    """
    运行竞赛脚本，执行编译好的CC文件
    :return: bool, 是否运行成功
    """
    task_id = task.task_id
    program_script = "./run-contest.sh"
    task.update(task_status=TaskStatus.RUNNING)
    # 该脚本接收9个参数，running_port uplink_file downlink_file result_path sender_path receiver_path loss_rate buffer_size delay
    # 运行端口 上行文件 下行文件 结果路径 发送端路径 接收端路径 丢包率 缓冲区大小 时延
    _config = config.get_course_config(task.cname)
    loss_rate = task.loss_rate
    buffer_size = task.buffer_size
    delay = task.delay
    uplink_dir = _config['uplink_dir']
    downlink_dir = _config['downlink_dir']
    uplink_file = uplink_dir + "/" + task.trace_name + ".up"
    downlink_file = downlink_dir + "/" + task.trace_name + ".down"
    run_cmd(
        f"cd {course_project_dir} && {program_script} {running_port} {uplink_file} {downlink_file} {result_path} {sender_path} {receiver_path} {loss_rate} {buffer_size} {delay}",
        task_id)
    logger.info(f"[task: {task_id}] run-contest.sh completed successfully")


def _remove_binary_files(task_id, sender_path, receiver_path):
    """
    删除编译生成的二进制文件
    :param task_id: 任务ID
    :param sender_path: 发送端路径
    :param receiver_path: 接收端路径
    :return: None
    """
    logger.debug(f"[task: {task_id}] Removing sender and receiver binary files")
    if os.path.exists(sender_path):
        os.remove(sender_path)
        logger.info(f"[task: {task_id}] Removed sender binary file: {sender_path}")
    if os.path.exists(receiver_path):
        os.remove(receiver_path)
        logger.info(f"[task: {task_id}] Removed receiver binary file: {receiver_path}")


def _get_score(task, result_path):
    """
    获取评分
    :return: None or float, 返回评分，如果失败则返回None
    """
    task_id = task.task_id
    extract_program = "mm-throughput-graph"
    logger.debug(f"[task: {task_id}] is getting score from {result_path} using {extract_program}")
    run_cmd(
        f'{extract_program} 500 {result_path} 2> {task.task_dir}/{task.trace_name}.score > /dev/null',
        task_id)
    total_score = evaluate_score(task, f'{task.task_dir}/{task.trace_name}.score')
    total_score = round(total_score, 4)
    logger.debug(f"[task: {task_id}] Score extracted successfully: {total_score}")
    return total_score


def _graph(task, result_path):
    """
    画图
    :return: None
    """
    task_id = task.task_id

    throughput_graph_svg = os.path.join(task.task_dir, f"{task.trace_name}.throughput.svg")
    delay_graph_svg = os.path.join(task.task_dir, f"{task.trace_name}.delay.svg")
    delay_graph_png = os.path.join(task.task_dir, f"{task.trace_name}.delay.png")
    # 另一个画图逻辑
    # tunnel_graph = TunnelGraph(
    #     tunnel_log=result_path,
    #     throughput_graph=task.task_dir + "/" + task.trace_name + ".throughput.png",
    #     delay_graph=task.task_dir + "/" + task.trace_name + ".delay.png",
    #     ms_per_bin=500)
    # tunnel_graph.run()
    logger.info(f"[task: {task_id}] is generating graphs")
    run_cmd(f'mm-throughput-graph 500 {result_path} > {throughput_graph_svg}', task_id)
    run_cmd(f'mm-delay-graph {result_path} > {delay_graph_svg}', task_id)
    # 由于delay svg图太大，将svg转换为png以压缩
    logger.info(f"[task: {task_id}] Converting delay graph SVG to PNG")
    cairosvg.svg2png(url=delay_graph_svg, write_to=delay_graph_png)
    os.remove(delay_graph_svg)
    logger.info(f"[task: {task_id}] Converted delay graph SVG to PNG, svg removed.")
    logger.info(f"[task: {task_id}] Graphs generated successfully: {throughput_graph_svg}, {delay_graph_png}")
    GraphModel(task_id=task_id, graph_type=GraphType.THROUGHPUT,
               graph_path=throughput_graph_svg).insert()
    GraphModel(task_id=task_id, graph_type=GraphType.DELAY,
               graph_path=delay_graph_png).insert()
    logger.info(f"[task: {task_id}] is generating graphs successfully")


def _update_rank(task, user):
    """
    更新榜单
    :param task: Task_model对象
    :param user: User_model对象
    :return: True if all tasks are completed and tried to update rank, False otherwise
    """
    task_id = task.task_id
    upload_id = task.upload_id

    # 创建用户级别的分布式锁
    lock_name = f'rank_update_lock_{task.user_id}_{task.cname}'
    rank_lock = Lock(redis_client, lock_name, timeout=30)  # 30秒超时
    logger.info(f"[task: {task_id}] Acquired rank update lock: {lock_name}")

    with rank_lock:
        logger.info(f"[task: {task_id}] try to update rank")
        # 获取该 upload_id 下的所有任务
        all_tasks = TaskModel.query.filter_by(upload_id=upload_id).all()
        # 检查是否所有任务都已完成
        all_tasks_completed = all(t.task_status == TaskStatus.FINISHED for t in all_tasks)

        if not all_tasks_completed:
            logger.warning(f"[task: {task_id}] Not all tasks completed for upload_id {upload_id}, skipping rank update")
            return False

        # 计算所有任务的总分
        total_upload_score = sum(t.task_score for t in all_tasks if t.task_score is not None)
        # 获取用户当前课程的榜单记录
        rank_record = RankModel.query.filter_by(competition_id=task.competition_id).first()
        logger.debug(
            f"[task: {task_id}] is updating rank record: {rank_record}, user: {user.username}, competition_id: {task.competition_id}")
        if rank_record:
            # 如果已有记录，检查是否需要更新
            # if rank_record.upload_time < task.created_time:
            # 如果已有记录，检查是否需要更新（基于分数而不是时间）
            if total_upload_score > rank_record.task_score:
                # 当前分数更高，更新记录
                rank_record.update(
                    upload_id=upload_id,
                    task_score=total_upload_score,
                    algorithm=task.algorithm,
                    upload_time=task.created_time
                )
                logger.info(
                    f"[task: {task_id}] Updated rank record with higher score: {total_upload_score} (previous: {rank_record.task_score}), user: {user.username}, competition_id: {task.competition_id}")
            else:
                # 当前分数更低，不更新记录
                logger.warning(
                    f"[task: {task_id}] Skipping rank update as current score {total_upload_score} is lower than existing score {rank_record.task_score}, user: {user.username}, competition_id: {task.competition_id}")
        else:
            # 没有记录，创建新记录
            RankModel(
                user_id=task.user_id,
                upload_id=upload_id,
                competition_id=task.competition_id,
                task_score=total_upload_score,
                algorithm=task.algorithm,
                upload_time=task.created_time,
                cname=task.cname,
                username=user.username
            ).insert()
            logger.info(
                f"[task: {task_id}] Created new rank record for user: {user.username}, score: {total_upload_score}, competition_id: {task.competition_id}")

        logger.info(
            f"[task: {task_id}] Rank update completed for upload_id: {upload_id}, user: {user.username}, competition_id: {task.competition_id}")
        return True


@dramatiq.actor(time_limit=1200000, max_retries=0)
def run_cc_training_task(task_id):
    app = get_app()
    with (app.app_context()):
        try:
            db.session.expire_all()  # 刷新会话
            task = TaskModel.query.filter_by(task_id=task_id).first()
            if not task:
                logger.error(f"[task: {task_id}] Task not found")
                return

            logger.info(f"[task: {task_id}] Start task")
            assert task.task_status == TaskStatus.QUEUED, "Task status must be QUEUED to run"
            user = UserModel.query.filter_by(user_id=task.user_id).first()

            # 课程的项目目录，公共目录
            _config = config.get_course_config(task.cname)
            course_project_dir = os.path.join(_config['path'], 'project', 'datagrump')
            # 本次任务的父级（对应一次提交）目录
            task_parent_dir = os.path.dirname(task.task_dir)
            sender_path = os.path.join(task_parent_dir, 'sender')
            receiver_path = os.path.join(task_parent_dir, 'receiver')

            # 因为编译需要单独处理任务状态，所以没有直接抛出异常，抛出异常会导致任务状态变为ERROR
            if not _compile_cc_file(task, course_project_dir, task_parent_dir, sender_path,
                                    receiver_path):
                logger.error(f"[task: {task_id}] compile cc file failed, task will not run")
                return

            # 编译好后再创建task（trace）目录
            if not os.path.exists(task.task_dir):
                os.mkdir(task.task_dir)
                logger.info(f"[task: {task_id}] Created task dir: {task.task_dir}")

            result_path = os.path.join(task.task_dir, task.trace_name + ".log")

            running_port = get_available_port(redis_client)
            logger.info(f"[task: {task_id}] select port {running_port} for running")
            _run_contest(task, course_project_dir, sender_path, receiver_path, result_path, running_port)

            total_score = _get_score(task, result_path)

            _graph(task, result_path)

            task.update(task_status=TaskStatus.FINISHED, task_score=total_score)
            # 更新完状态后再更新榜单，如果榜单更新失败，任务状态会回退至ERROR
            all_tasks_completed = _update_rank(task, user)
            if all_tasks_completed:
                _remove_binary_files(task_id, sender_path, receiver_path)
            logger.info(f"[task: {task_id}] Task completed successfully, score: {total_score}")
        except Exception as e:
            # 理论上除了编译失败外，不应出现其他异常，如果出现，需要修复代码相关逻辑
            err_msg = f"{type(e).__name__}\n{str(e)}"
            task_error_log_content = f"发生意外错误，请将此信息反馈给管理员协助排查。\n[task_id: {task_id}]\nException occurred:\n{err_msg}\n"
            logger.error(f"[task: {task_id}] {task_error_log_content}", exc_info=True)
            if 'task' in locals() and task:
                # 日志长度和数据库设置的长度计算方式不同，这里限制为8000
                if len(task_error_log_content) > 8000:
                    task_error_log_content = task_error_log_content[:8000] + '...'
                task.update(task_status=TaskStatus.ERROR, error_log=task_error_log_content)
                logger.error(f"[task: {task_id}] Task status updated to ERROR due to exception")
            # 删除编译生成的二进制文件，注意不在finally中删除，因为正常结束的任务不一定需要删除，其他任务可能会复用
            if 'sender_path' in locals() and 'receiver_path' in locals():
                _remove_binary_files(task_id, sender_path, receiver_path)
        finally:
            try:
                db.session.remove()
                if 'running_port' in locals():
                    release_port(running_port, redis_client)
                # remove log file if exists
                if 'result_path' in locals() and os.path.exists(result_path):
                    os.remove(result_path)
                    logger.info(f"[task: {task_id}] Removed result file: {result_path}")

            except Exception as e:
                logger.error(f"[task: {task_id}] Error when finally cleanup: {str(e)}", exc_info=True)


def _force_kill_process_group(process, task_id):
    """
    使用 SIGKILL 强制终止进程组
    :param process: subprocess.Popen 对象
    :param task_id: 任务ID
    :return: None
    """
    try:
        logger.info(f"[task: {task_id}] Attempting to kill process group for PID: {process.pid}")
        pgid = os.getpgid(process.pid)
        os.killpg(pgid, signal.SIGKILL)
        logger.info(f"[task: {task_id}] Process group killed successfully")
    except ProcessLookupError:
        logger.info(f"[task: {task_id}] Process group already terminated")
    except Exception as e:
        logger.error(f"[task: {task_id}] Failed to kill process group: {str(e)}")


def run_cmd(cmd, task_id, raise_exception=True):
    logger.info(f"[task: {task_id}] Running command: {cmd}")
    timeout = 600  # 设置超时时间为10分钟（600秒）
    shell = True
    commands_str = ""

    try:
        if isinstance(cmd, list):
            shell = False
            commands_str = cmd[0]
        else:
            # 如果是字符串，分割成多个命令，不显示具体参数给用户
            commands = [c.strip().split()[0] for c in cmd.split('&&')]
            commands_str = '; '.join(commands)

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=shell,
            preexec_fn=os.setsid  # 创建新的进程组
        )

        try:
            stdout, stderr = process.communicate(timeout=timeout)
            # 限制输出长度，避免用户代码内的输出过多内容影响系统日志
            stdout = stdout[:16000]
            stderr = stderr[:16000]
            output = f"stderr:\n{stderr}\nstdout:\n{stdout}\n"
            logger.info(f"[task: {task_id}] Command output: {output}")

            if process.returncode != 0:
                logger.error(
                    f"[task: {task_id}] Command failed with return code {process.returncode}")
                if raise_exception:
                    raise RuntimeError(f"Command failed: {commands_str}\n\n{output}")
                return False, output

            logger.info(f"[task: {task_id}] Command completed successfully")
            return True, output

        except subprocess.TimeoutExpired:
            # 超时时，终止整个进程组
            logger.error(f"[task: {task_id}] Command timed out after {timeout} seconds, terminating process group")
            _force_kill_process_group(process, task_id)
            raise RuntimeError(f"Command timed out after {timeout} seconds: {commands_str}")

    except Exception as e:
        # 确保进程被终止
        assert 'process' in locals(), "Process object not found, cannot terminate"
        _force_kill_process_group(process, task_id)
        # 抛出异常，保证任务状态正确更新
        raise e


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
    logger.info(f"[task: {task_id}] Enqueueing task")
    try:
        # 发送任务到队列
        message = run_cc_training_task.send(task_id)

        # 检查消息是否成功创建
        if message and hasattr(message, 'message_id'):
            logger.info(f"[task: {task_id}] Successfully enqueued with message ID: {message.message_id}")
            return {
                'success': True,
                'message': 'Task successfully enqueued',
                'message_id': message.message_id,
                'task_id': task_id
            }
        else:
            logger.error(f"[task: {task_id}] Failed to enqueue: No message ID returned")
            return {
                'success': False,
                'message': 'Failed to enqueue task: No message ID returned',
                'message_id': None,
                'task_id': task_id
            }

    except Exception as e:
        logger.error(f"[task: {task_id}] Failed to enqueue: {str(e)}", exc_info=True)
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


def evaluate_score(task: TaskModel, score_file: str):
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
