import logging
import os
import shutil
import signal
import subprocess

import dramatiq
from app_backend.jobs.dramatiq_queue import DramatiqQueue
from app_backend.jobs.graph_job import run_graph_task
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware.time_limit import TimeLimitExceeded
from redis.lock import Lock

from app_backend import db, redis_client, get_default_config
from app_backend import get_app
from app_backend.analysis.score_evaluate import evaluate_score
from app_backend.jobs.dramatiq_queue import DramatiqQueue
from app_backend.jobs.graph_job import run_graph_task
from app_backend.model.rank_model import RankModel
from app_backend.model.task_model import TaskModel, TaskStatus
from app_backend.model.user_model import UserModel
from app_backend.utils.utils import get_available_port, release_port, setup_logger

# 设置日志记录器
setup_logger()
logger = logging.getLogger(__name__)
config = get_default_config()
redis_broker = RedisBroker(url=config.Cache.FLASK_REDIS_URL)
dramatiq.set_broker(redis_broker)


# 20分钟超时（毫秒），此时间应大于cmd子进程的超时时间
@dramatiq.actor(time_limit=1200000, max_retries=0, queue_name=DramatiqQueue.CC_TRAINING.value)
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

            # _graph(task, result_path)
            # 将图生成任务放入队列，异步执行
            message = run_graph_task.send(task_id, result_path)
            if not message:
                logger.error(f"[task: {task_id}] Failed to enqueue graph task")
                task.update_task_log("流量图绘制任务无法生成，如有需要请联系管理员。")
            else:
                logger.info(f"[task: {task_id}] Graph task enqueued successfully with message ID: {message.message_id}")
                task.update_task_log(
                    "流量图绘制任务已生成，请稍后再查询性能图，高峰时期可能需要等待较长时间，等待期间，可从任务日志中查询最新进度。")

            task.update(task_status=TaskStatus.FINISHED, task_score=total_score)
            # 更新完状态后再更新榜单，如果榜单更新失败，任务状态会回退至ERROR
            all_tasks_completed = _update_rank(task, user)
            if all_tasks_completed:
                _remove_binary_files(task_id, sender_path, receiver_path)
            logger.info(f"[task: {task_id}] Task completed successfully, score: {total_score}")
        except TimeLimitExceeded as e:
            # 处理 Dramatiq 的超时异常，此异常不在Exception中，需单独处理
            logger.error(f"[task: {task_id}] Task timed out due to Dramatiq TimeLimit middleware")
            err_msg = f"{type(e).__name__}\n{str(e)}\nTask timed out after 20 minutes, this problem shouldn't happen, please contact admin."

            _task = None
            _sender_path = None
            _receiver_path = None
            if 'task' in locals():
                _task = task
            if 'sender_path' in locals() and 'receiver_path' in locals():
                _sender_path = sender_path
                _receiver_path = receiver_path
            _handle_exception(task_id, err_msg, _task, _sender_path, _receiver_path)

        except Exception as e:
            # 理论上除了编译失败外，不应出现其他异常，如果出现，需要修复代码相关逻辑
            err_msg = f"{type(e).__name__}\n{str(e)}"

            _task = None
            _sender_path = None
            _receiver_path = None
            if 'task' in locals():
                _task = task
            if 'sender_path' in locals() and 'receiver_path' in locals():
                _sender_path = sender_path
                _receiver_path = receiver_path
            _handle_exception(task_id, err_msg, _task, _sender_path, _receiver_path)
        finally:
            try:
                db.session.remove()
                if 'running_port' in locals():
                    release_port(running_port, redis_client)

            except TimeLimitExceeded as e:
                logger.error(f"[task: {task_id}] Error when finally cleanup: Dramatiq TimeLimitExceeded", exc_info=True)
            except Exception as e:
                logger.error(f"[task: {task_id}] Error when finally cleanup: {str(e)}", exc_info=True)


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
            task.update_task_log(
                "本次提交的代码在其他任务中编译失败，此任务不再尝试编译，如需查询编译日志，请查询本次提交下的其他任务。")
            task.update(task_status=TaskStatus.ERROR)
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
                task.update_task_log(f"Compilation failed, make output:\n\n{output}")
                task.update(task_status=TaskStatus.COMPILED_FAILED)
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
    trace_conf = config.get_course_trace_config(task.cname, task.trace_name)
    assert trace_conf is not None, f"Trace configuration for {task.cname} and {task.trace_name} not found"
    uplink_file = os.path.join(_config['trace_path'], trace_conf['uplink_file'])
    downlink_file = os.path.join(_config['trace_path'], trace_conf['downlink_file'])
    _, output = run_cmd(
        f"cd {course_project_dir} && {program_script} {running_port} {uplink_file} {downlink_file} {result_path} {sender_path} {receiver_path} {loss_rate} {buffer_size} {delay}",
        task_id)
    logger.info(f"[task: {task_id}] run-contest.sh completed successfully")
    task.update_task_log(f"Contest done, program logs:\n\n{output}")


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


def _handle_exception(task_id, err_msg, task=None, sender_path=None, receiver_path=None):
    """
    处理异常，更新任务状态和错误日志
    :param task: TaskModel对象
    :param task_id: 任务ID
    :param err_msg: 错误信息
    """
    task_error_log_content = f"发生意外错误，请稍后再试。若问题仍存在可将此信息反馈给管理员协助排查。\n[task_id: {task_id}]\nException occurred:\n{err_msg}\n"
    logger.error(f"[task: {task_id}] {task_error_log_content}", exc_info=True)
    if task:
        task.update_task_log(task_error_log_content)
        task.update(task_status=TaskStatus.ERROR)
        logger.error(f"[task: {task_id}] Task status updated to ERROR due to exception")
    # 删除编译生成的二进制文件，注意不在finally中删除，因为正常结束的任务不一定需要删除，其他任务可能会复用
    if sender_path and receiver_path:
        _remove_binary_files(task_id, sender_path, receiver_path)


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
            # 打印日志时限制输出长度，避免用户代码内的输出过多内容影响系统日志
            logger.info(f"[task: {task_id}] Command output: \nstdout:\n{stdout[:6000]}\nstderr:\n{stderr[:6000]}\n")
            # 脱敏处理输出中的路径和敏感命令参数
            output = f"stdout:\n{stdout}\nstderr:\n{stderr}\n"

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
