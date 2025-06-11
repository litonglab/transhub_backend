import logging
import os
import time
import uuid
from datetime import datetime

from flask import Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from app_backend import get_default_config
from app_backend.decorators.validators import validate_request, get_validated_data
from app_backend.jobs.cctraining_job import enqueue_cc_task
from app_backend.model.Task_model import Task_model, TaskStatus
from app_backend.model.User_model import User_model
from app_backend.utils.utils import generate_random_string
from app_backend.validators.schemas import TaskInfoSchema, FileUploadSchema
from app_backend.vo import HttpResponse

task_bp = Blueprint('task', __name__)
logger = logging.getLogger(__name__)
config = get_default_config()


# check_illegal 函数已移动到 FileUploadSchema.validate_file_content_safety 中


@task_bp.route("/task_upload", methods=["POST"])
@jwt_required()
@validate_request(FileUploadSchema)
def upload_project_file():
    cname = get_jwt().get('cname')
    _config = config.Course.ALL_CLASS[cname]
    start_time = time.mktime(time.strptime(_config['start_time'], "%Y-%m-%d-%H-%M-%S"))
    ddl_time = time.mktime(time.strptime(_config['end_time'], "%Y-%m-%d-%H-%M-%S"))
    now_time = time.time()

    logger.debug(f"File upload attempt for competition {cname}")

    # 检查当前时间是否在比赛时间范围内
    if not (start_time <= now_time <= ddl_time):
        logger.warning(
            f"Upload rejected: Outside competition period. Current time: {now_time}, Start: {start_time}, End: {ddl_time}")
        return HttpResponse.fail(f"Current time is not within the competition period. "
                                 f"Competition starts at {_config['start_time']} and ends at {_config['end_time']}.")

    # 获取验证后的数据
    data = get_validated_data(FileUploadSchema)
    file = data.file
    user_id = get_jwt_identity()  # 用户id
    # 从token中获取cname
    cname = get_jwt().get('cname')

    # 文件已经通过 Pydantic 验证，直接获取文件信息
    filename = file.filename
    algorithm = filename.split('.')[0]

    logger.info(f"Processing upload for user {user_id}, file: {filename}, algorithm: {algorithm}")

    user = User_model.query.get(user_id)
    if not user:
        logger.warning(f"Upload failed: User {user_id} not found")
        return HttpResponse.fail("User not found.")

    now = datetime.now()
    upload_dir_name = f"{now.strftime("%Y-%m-%d-%H-%M-%S")}_{generate_random_string(6)}"

    temp_dir = user.save_file_to_user_dir(file, cname, upload_dir_name)
    upload_id = str(uuid.uuid1())
    # 构建task,按trace和env构建多个task
    task_ids = []

    uplink_dir = _config['uplink_dir']
    enqueue_results = []  # 收集所有入队结果
    failed_tasks = []  # 记录失败的任务

    logger.info(f"Starting task creation for upload {upload_id}")

    for trace_file in os.listdir(uplink_dir):
        trace_name = trace_file[:-3]
        for loss in _config['loss_rate']:
            for buffer_size in _config['buffer_size']:
                task_id = str(uuid.uuid1())
                task = Task_model(task_id=task_id, user_id=user_id, task_status=TaskStatus.QUEUED.value, task_score=0,
                                  created_time=now.strftime("%Y-%m-%d-%H-%M-%S"), cname=cname,
                                  task_dir=os.path.join(temp_dir, f"{trace_name}_{loss}_{buffer_size}"),
                                  algorithm=algorithm, trace_name=trace_name, upload_id=upload_id, loss_rate=loss,
                                  buffer_size=buffer_size)

                # 保存任务到数据库
                task.save()
                task_ids.append(task_id)
                logger.debug(
                    f"[task: {task_id}] Created task for trace {trace_name}, loss {loss}, buffer {buffer_size}")

                # 发送任务到队列并检查结果
                enqueue_result = enqueue_cc_task(task_id)
                enqueue_results.append(enqueue_result)

                if not enqueue_result['success']:
                    # 如果入队失败，更新任务状态为错误
                    task.update(task_status=TaskStatus.NOT_QUEUED.value)
                    failed_tasks.append({
                        'task_id': task_id,
                        'trace_name': trace_name,
                        'loss_rate': loss,
                        'buffer_size': buffer_size,
                        'error': enqueue_result['message']
                    })
                    logger.error(f"[task: {task_id}] Failed to enqueue: {enqueue_result['message']}")
                else:
                    logger.info(
                        f"[task: {task_id}] Successfully enqueued with message ID: {enqueue_result['message_id']}")

    # 统计入队结果
    successful_enqueues = sum(1 for result in enqueue_results if result['success'])
    total_tasks = len(enqueue_results)

    logger.info(f"Upload {upload_id} completed: {successful_enqueues}/{total_tasks} tasks successfully enqueued")

    # 构建响应消息
    if len(failed_tasks) > 0:
        message = f"Upload completed. {successful_enqueues}/{total_tasks} tasks successfully enqueued."
        logger.error(f"Upload {upload_id} : some tasks failed to enqueue")
    else:
        message = f"Upload success. All {total_tasks} tasks successfully enqueued."
    return HttpResponse.ok(
        message=message,
        filename=filename,
        tasks=task_ids,
        upload_id=upload_id,
        enqueue_summary={
            'total_tasks': total_tasks,
            'successful_enqueues': successful_enqueues,
            'failed_enqueues': len(failed_tasks),
            'failed_tasks': failed_tasks
        }
    )


@task_bp.route("/task_get_task_info", methods=["POST"])
@jwt_required()
@validate_request(TaskInfoSchema)
# not used now.
def return_task():
    data = get_validated_data(TaskInfoSchema)
    task_id = data.task_id
    user_id = get_jwt_identity()

    logger.debug(f"[task: {task_id}] Task info request by user {user_id}")

    # 保证只能查询自己的任务
    task_info = Task_model.query.filter_by(task_id=task_id, user_id=user_id).first()
    if not task_info:
        logger.warning(f"[task: {task_id}] Task info request failed: Task not found for user {user_id}")
        return HttpResponse.fail("Task not found.")

    task_status = TaskStatus(task_info.task_status)
    if task_status == TaskStatus.QUEUED:
        logger.debug(f"[task: {task_id}] Task is still queued")
        return HttpResponse.ok("Task is queued.")

    if task_status == TaskStatus.ERROR:
        # 从task_dir中读取error.log,返回给前端
        try:
            with open(f'{task_info.task_dir}/error.log', 'r') as f:
                error_info = f.read()
            logger.error(f"[task: {task_id}] Error details: {error_info}")
            return HttpResponse.ok("Task error", error_info=error_info)
        except Exception as e:
            error_info = str(e)
            return HttpResponse.ok("Task error", error_info=error_info)

    task_res = task_info.to_detail_dict()
    logger.debug(f"[task: {task_id}] Successfully retrieved task info")
    return HttpResponse.ok("Task info found.", task_res=task_res)
