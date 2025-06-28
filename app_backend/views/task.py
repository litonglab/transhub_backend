import logging
import os
import uuid
from datetime import datetime

from flask import Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from app_backend import get_default_config
from app_backend.jobs.cctraining_job import enqueue_cc_task
from app_backend.model.task_model import TaskModel, TaskStatus
from app_backend.model.user_model import UserModel
from app_backend.utils.utils import generate_random_string
from app_backend.validators.decorators import validate_request, get_validated_data
from app_backend.validators.schemas import FileUploadSchema
from app_backend.vo.http_response import HttpResponse

task_bp = Blueprint('task', __name__)
logger = logging.getLogger(__name__)
config = get_default_config()


# check_illegal 函数已移动到 FileUploadSchema.validate_file_content_safety 中


@task_bp.route("/task_upload", methods=["POST"])
@jwt_required()
@validate_request(FileUploadSchema)
def upload_project_file():
    user_id = get_jwt_identity()
    cname = get_jwt().get('cname')
    logger.debug(f"File upload attempt for competition {cname} by user {user_id}")

    # 检查当前时间是否在比赛时间范围内
    if not config.is_now_in_competition(cname):
        logger.warning(
            f"Upload rejected: Outside competition period.")
        return HttpResponse.fail(f"比赛尚未开始或已截止，请在比赛时间内上传代码。")

    # 获取验证后的数据
    data = get_validated_data(FileUploadSchema)
    file = data.file

    # 文件已经通过 Pydantic 验证，直接获取文件信息
    filename = file.filename
    algorithm = filename.split('.')[0]

    logger.info(f"Processing upload for user {user_id}, file: {filename}, algorithm: {algorithm}")

    user = UserModel.query.get(user_id)
    if not user:
        logger.warning(f"Upload failed: User {user_id} not found")
        return HttpResponse.not_found("用户不存在")

    now_str = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
    upload_dir_name = f"{now_str}_{generate_random_string(6)}"

    temp_dir = user.save_file_to_user_dir(file, cname, upload_dir_name)
    upload_id = str(uuid.uuid1())
    # 构建task,按trace和env构建多个task
    task_ids = []

    # 获取课程的 trace 文件列表
    trace_files = config.get_course_trace_files(cname)
    enqueue_results = []  # 收集所有入队结果
    failed_tasks = []  # 记录失败的任务

    logger.info(f"Starting task creation for upload {upload_id}")

    for trace_name in trace_files:
        trace_conf = config.get_course_trace_config(cname, trace_name)
        for loss in trace_conf['loss_rate']:
            for buffer_size in trace_conf['buffer_size']:
                task_id = str(uuid.uuid1())
                task = TaskModel(task_id=task_id, user_id=user_id, task_status=TaskStatus.QUEUED.value, task_score=0,
                                 created_time=now_str, cname=cname,
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
        message = f"上传成功，{successful_enqueues}/{total_tasks}个任务已入队，部分任务已丢失。"
        logger.error(f"Upload {upload_id} : some tasks failed to enqueue")
    else:
        message = f"上传成功，{total_tasks}个任务已入队。"
    return HttpResponse.ok(
        message=message,
        tasks=task_ids,
        upload_id=upload_id,
        enqueue_summary={
            'total_tasks': total_tasks,
            'successful_enqueues': successful_enqueues,
            'failed_enqueues': len(failed_tasks),
            'failed_tasks': failed_tasks
        }
    )
