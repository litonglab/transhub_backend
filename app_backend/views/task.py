import logging
import os
import uuid
from datetime import datetime

from flask import Blueprint
from flask_jwt_extended import jwt_required, get_jwt, current_user

from app_backend import get_default_config, cache
from app_backend.jobs.cctraining_job import enqueue_cc_task
from app_backend.model.competition_model import CompetitionModel
from app_backend.model.task_model import TaskModel, TaskStatus
from app_backend.security.bypass_decorators import admin_bypass
from app_backend.utils.utils import generate_random_string
from app_backend.utils.utils import get_record_by_permission
from app_backend.validators.decorators import validate_request, get_validated_data
from app_backend.validators.schemas import EnqueueTaskSchema
from app_backend.validators.schemas import FileUploadSchema, TaskLogSchema
from app_backend.vo.http_response import HttpResponse

task_bp = Blueprint('task', __name__)
logger = logging.getLogger(__name__)
config = get_default_config()


@admin_bypass
def _check_upload_not_exceeds_limit(user, cname, max_active_uploads_per_user):
    """
    检查用户当前课程处于运行中或者队列中的任务数量，同一个upload_id只算一次
    如果没超过，返回True，表示可以继续上传，否则返回False
    """
    running_or_queued_uploads = (
        TaskModel.query.filter(
            TaskModel.user_id == user.user_id,
            TaskModel.cname == cname,
            TaskModel.task_status.in_([TaskStatus.RUNNING, TaskStatus.QUEUED])
        )
        .with_entities(TaskModel.upload_id).distinct().count()
    )
    if running_or_queued_uploads >= max_active_uploads_per_user:
        logger.warning(
            f"Upload rejected: User {user.username} has {running_or_queued_uploads} running or queued uploads, exceeds limit {max_active_uploads_per_user}.")
        return False
    return True


@task_bp.route("/task_upload", methods=["POST"])
@jwt_required()
@validate_request(FileUploadSchema)
def upload_project_file():
    user = current_user
    cname = get_jwt().get('cname')
    logger.debug(f"File upload attempt for competition {cname} by user {user.username}")

    # 检查当前时间是否在比赛时间范围内
    if not config.is_now_in_competition(cname):
        logger.warning(
            f"Upload rejected: Outside competition period.")
        return HttpResponse.fail(f"比赛尚未开始或已截止，请在比赛时间内上传代码。")

    # 查询用户当前课程处于运行中或者队列中的任务数量，同一个upload_id只算一次
    max_active_uploads_per_user = config.get_course_config(cname)['max_active_uploads_per_user']
    if not _check_upload_not_exceeds_limit(user, cname, max_active_uploads_per_user):
        return HttpResponse.fail(
            f"你在当前课程（比赛）{cname}中处于排队或运行状态的提交数量已达到上限（{max_active_uploads_per_user}），请等待运行完成后再提交。")

    # 获取验证后的数据
    data = get_validated_data(FileUploadSchema)
    trace_list = data.trace_list
    file = data.file

    # 文件已经通过 Pydantic 验证，直接获取文件信息
    filename = file.filename
    algorithm = filename.rsplit('.', 1)[0]

    logger.info(f"Processing upload for user {user.username}, file: {filename}, algorithm: {algorithm}")

    now_str = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
    upload_dir_name = f"{now_str}_{generate_random_string(6)}"

    upload_dir = user.save_file_to_user_dir(file, cname, upload_dir_name)
    upload_id = str(uuid.uuid1())
    # 构建task,按trace和env构建多个task
    task_ids = []

    enqueue_results = []  # 收集所有入队结果
    failed_tasks = []  # 记录失败的任务
    competition_id = (CompetitionModel.query.filter_by(cname=cname, user_id=user.user_id)
                      .first().id)

    logger.info(
        f"Starting task creation for upload {upload_id}, user {user.username}, cname {cname}, competition_id {competition_id}")

    _config = config.get_course_config(cname)
    for trace_name, trace_conf in _config['trace'].items():
        loss = trace_conf['loss_rate']
        buffer_size = trace_conf['buffer_size']
        delay = trace_conf['delay']
        task = TaskModel(user_id=user.user_id, task_status=TaskStatus.NOT_QUEUED,
                         task_score=0, created_time=now_str, cname=cname, competition_id=competition_id,
                         task_dir=os.path.join(upload_dir, f"{trace_name}_{loss}_{buffer_size}_{delay}"),
                         algorithm=algorithm, trace_name=trace_name, upload_id=upload_id,
                         loss_rate=loss, buffer_size=buffer_size, delay=delay, error_log='')

        # 保存任务到数据库
        task.save()
        task_ids.append(task.task_id)
        logger.debug(
            f"[task: {task.task_id}] Created task for trace {trace_name}, loss {loss}, buffer {buffer_size}")

        # 发送任务到队列并检查结果
        if trace_name not in trace_list:
            continue  # 如果trace不在用户选择的列表中，跳过此trace
        enqueue_result = enqueue_cc_task(task.task_id)
        enqueue_results.append(enqueue_result)

        if not enqueue_result['success']:
            failed_tasks.append({
                'task_id': task.task_id,
                'trace_name': trace_name,
                'loss_rate': loss,
                'buffer_size': buffer_size,
                'error': enqueue_result['message']
            })
            logger.error(f"[task: {task.task_id}] Failed to enqueue: {enqueue_result['message']}")
        else:
            task.update(task_status=TaskStatus.QUEUED)
            logger.info(
                f"[task: {task.task_id}] Successfully enqueued with message ID: {enqueue_result['message_id']}")

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


# 获取任务日志接口
@task_bp.route("/task_get_log", methods=["GET"])
@jwt_required()
@validate_request(TaskLogSchema)
def get_task_log():
    data = get_validated_data(TaskLogSchema)
    task_id = data.task_id
    task = TaskModel.query.filter_by(task_id=task_id).first()
    if not task:
        logger.warning(f"Task log request: Task {task_id} not found")
        return HttpResponse.not_found("任务不存在")
    # 权限校验
    if not task.log_permission():
        logger.warning(f"Task log request: User {current_user.username} has no permission for task {task_id}")
        return HttpResponse.forbidden("无权限访问该任务日志")
    logger.info(f"User {current_user.username} fetched log for task {task_id}")
    return HttpResponse.ok(log=task.error_log)


@cache.memoize(timeout=60)
def _trace_list_cache(cname):
    """获取当前课程的Trace列表缓存"""
    _config = config.get_course_config(cname)
    trace_config = _config.get('trace', {})
    trace_list = []
    for trace_name, trace_conf in trace_config.items():
        is_blocked = trace_conf.get('block', False)
        trace_list.append({
            'trace_name': trace_name,
            'is_blocked': is_blocked
        })
    return trace_list


# 获取当前课程的Trace列表接口
@task_bp.route("/task_get_trace_list", methods=["GET"])
@jwt_required()
def get_trace_list():
    cname = get_jwt().get('cname')
    trace_list = _trace_list_cache(cname)
    logger.debug(f"User {current_user.username} fetched trace list for course {cname}: {trace_list}")
    return HttpResponse.ok(trace_list=trace_list)


@task_bp.route("/task_enqueue", methods=["POST"])
@jwt_required()
@validate_request(EnqueueTaskSchema)
def enqueue_task():
    data = get_validated_data(EnqueueTaskSchema)
    task_id = data.task_id
    # 确保只能操作自己的任务
    task = get_record_by_permission(TaskModel, {"task_id": task_id})
    if not task:
        logger.warning(f"Enqueue task: Task {task_id} not found or no permission")
        return HttpResponse.not_found("任务不存在或无权限")
    if task.task_status != TaskStatus.NOT_QUEUED:
        logger.info(f"Enqueue task: Task {task_id} status is {task.task_status}, not NOT_QUEUED")
        return HttpResponse.fail("该任务已入队或已运行，无需重复入队")
    # 入队
    enqueue_result = enqueue_cc_task(task.task_id)
    if enqueue_result['success']:
        task.update(task_status=TaskStatus.QUEUED)
        logger.info(f"Task {task_id} successfully enqueued")
        return HttpResponse.ok()
    else:
        logger.error(f"Task {task_id} failed to enqueue: {enqueue_result['message']}")
        return HttpResponse.fail(f"任务入队失败: {enqueue_result['message']}")
