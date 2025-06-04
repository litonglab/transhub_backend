import os
import time
import uuid
from datetime import datetime

from flask import Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from app_backend import ALL_CLASS
from app_backend.decorators.validators import validate_request, get_validated_data
from app_backend.jobs.cctraining_job import enqueue_cc_task
from app_backend.model.Task_model import Task_model
from app_backend.model.User_model import User_model
from app_backend.validators.schemas import TaskInfoSchema, FileUploadSchema
from app_backend.vo import HttpResponse

task_bp = Blueprint('task', __name__)


# check_illegal 函数已移动到 FileUploadSchema.validate_file_content_safety 中


@task_bp.route("/task_upload", methods=["POST"])
@jwt_required()
@validate_request(FileUploadSchema)
def upload_project_file():
    cname = get_jwt().get('cname')
    config = ALL_CLASS[cname]
    start_time = time.mktime(time.strptime(config['start_time'], "%Y-%m-%d-%H-%M-%S"))
    ddl_time = time.mktime(time.strptime(config['end_time'], "%Y-%m-%d-%H-%M-%S"))
    now_time = time.time()
    # 检查当前时间是否在比赛时间范围内
    if not (start_time <= now_time <= ddl_time):
        return HttpResponse.fail(f"Current time is not within the competition period. "
                                 f"Competition starts at {config['start_time']} and ends at {config['end_time']}.")

    # 获取验证后的数据
    data = get_validated_data(FileUploadSchema)
    file = data.file
    user_id = get_jwt_identity()  # 用户id
    # 从token中获取cname
    cname = get_jwt().get('cname')
    config = ALL_CLASS[cname]

    # 文件已经通过 Pydantic 验证，直接获取文件信息
    filename = file.filename
    algorithm = filename.split('.')[0]

    user = User_model.query.get(user_id)
    if not user:
        return HttpResponse.fail("User not found.")
    now = datetime.now()
    user.save_file_to_user_dir(file, cname, now.strftime("%Y-%m-%d-%H-%M-%S"))
    temp_dir = user.get_user_dir(cname) + "/" + now.strftime("%Y-%m-%d-%H-%M-%S")
    upload_id = str(uuid.uuid1())
    # 构建task,按trace和env构建多个task
    task_ids = []

    uplink_dir = config['uplink_dir']
    enqueue_results = []  # 收集所有入队结果
    failed_tasks = []  # 记录失败的任务

    for trace_file in os.listdir(uplink_dir):
        trace_name = trace_file[:-3]
        for loss in config['loss_rate']:
            for buffer_size in config['buffer_size']:
                task_id = str(uuid.uuid1())
                task = Task_model(task_id=task_id, user_id=user_id, task_status='queued', task_score=0,
                                  created_time=now.strftime("%Y-%m-%d-%H-%M-%S"), cname=cname,
                                  task_dir=temp_dir + "/" + trace_name + "_" + str(loss) + "_" + str(buffer_size),
                                  algorithm=algorithm, trace_name=trace_name, upload_id=upload_id, loss_rate=loss,
                                  buffer_size=buffer_size)

                # 保存任务到数据库
                task.save()
                task_ids.append(task_id)

                # 发送任务到队列并检查结果
                enqueue_result = enqueue_cc_task(task_id)
                enqueue_results.append(enqueue_result)

                if not enqueue_result['success']:
                    # 如果入队失败，更新任务状态为错误
                    task.update(task_status='not_queued')
                    failed_tasks.append({
                        'task_id': task_id,
                        'trace_name': trace_name,
                        'loss_rate': loss,
                        'buffer_size': buffer_size,
                        'error': enqueue_result['message']
                    })
                    print(f"Failed to enqueue task {task_id}: {enqueue_result['message']}")
                else:
                    print(f"Task {task_id} successfully enqueued with message ID: {enqueue_result['message_id']}")

    # 统计入队结果
    successful_enqueues = sum(1 for result in enqueue_results if result['success'])
    total_tasks = len(enqueue_results)

    # 构建响应消息
    if len(failed_tasks) > 0:
        message = f"Upload completed. {successful_enqueues}/{total_tasks} tasks successfully enqueued."
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
def return_task():
    data = get_validated_data(TaskInfoSchema)
    task_id = data.task_id
    user_id = get_jwt_identity()

    # 保证只能查询自己的任务
    task_info = Task_model.query.filter_by(task_id=task_id, user_id=user_id).first()
    print(task_info)
    if not task_info:
        return HttpResponse.fail("Task not found.")

    if task_info.task_status == 'queued':
        return HttpResponse.ok("Task is queued.")

    if task_info.task_status == 'error':
        # 从task_dir中读取error.log,返回给前端
        try:
            with open(f'{task_info.task_dir}/error.log', 'r') as f:
                error_info = f.read()
            return HttpResponse.ok("Task error", error_info=error_info)
        except Exception as e:
            with open(f'{task_info.task_dir}/error.log', 'r') as f:
                error_info = str(e)
            return HttpResponse.ok("Task error", error_info=error_info)
    task_res = task_info.to_detail_dict()
    return HttpResponse.ok("Task info found.", task_res=task_res)
