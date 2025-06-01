import os
import time
import uuid
from datetime import datetime

from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from app_backend.config import DDLTIME
from app_backend.config import get_config_by_cname
from app_backend.decorators.validators import validate_request
from app_backend.jobs.cctraining_job import enqueue_cc_task
from app_backend.model.Task_model import Task_model
from app_backend.model.User_model import User_model
from app_backend.security.safe_check import check_task_auth
from app_backend.validators.schemas import TaskInfoSchema, FileUploadSchema
from app_backend.vo import HttpResponse
from app_backend.vo.HttpResponse import _my_response

task_bp = Blueprint('task', __name__)


# check_illegal 函数已移动到 FileUploadSchema.validate_file_content_safety 中


@task_bp.route("/task_upload", methods=["POST"])
@jwt_required()
@validate_request(FileUploadSchema)
def upload_project_file():
    ddl_time = time.mktime(time.strptime(DDLTIME, "%Y-%m-%d-%H-%M-%S"))
    if time.time() > ddl_time:
        return HttpResponse.error("The competition has ended.")

    # 获取验证后的数据
    data = request.validated_data
    file = data.file
    user_id = get_jwt_identity()  # 用户id
    # 从token中获取cname
    cname = get_jwt().get('cname')
    config = get_config_by_cname(cname)
    if not config:
        return HttpResponse.error("No such competition.")

    # 文件已经通过 Pydantic 验证，直接获取文件信息
    filename = file.filename

    user = User_model.query.get(user_id)
    if not user:
        return HttpResponse.error("User not found.")
    now = datetime.now()
    user.save_file_to_user_dir(file, cname, now.strftime("%Y-%m-%d-%H-%M-%S"))
    temp_dir = user.get_user_dir(cname) + "/" + now.strftime("%Y-%m-%d-%H-%M-%S")
    upload_id = str(uuid.uuid1())
    # 构建task,按trace和env构建多个task
    task_ids = []

    uplink_dir = config.uplink_dir
    for trace_file in os.listdir(uplink_dir):
        trace_name = trace_file[:-3]
        for loss in config.loss_rate:
            for buffer_size in config.buffer_size:
                task_id = str(uuid.uuid1())
                task = Task_model(task_id=task_id, user_id=user_id, task_status='queued', task_score=0,
                                  created_time=now.strftime("%Y-%m-%d-%H-%M-%S"), cname=cname,
                                  task_dir=temp_dir + "/" + trace_name + "_" + str(loss) + "_" + str(buffer_size),
                                  algorithm=filename[:-3], trace_name=trace_name, upload_id=upload_id, loss_rate=loss,
                                  buffer_size=buffer_size)

                # task = executor.submit(run_task, newfilename[:-3])
                # task = run_task.queue()
                # update_task_status(task_id, 'queued')
                task.save()
                task_ids.append(task_id)
                enqueue_cc_task(task_id)
    # return {"code": 200, "message": "Upload Success. Task is running.", "filename": filename, "task_id": task_id}
    return HttpResponse.ok(filename=filename, tasks=task_ids)


@task_bp.route("/task_get_task_info", methods=["POST"])
@jwt_required()
@validate_request(TaskInfoSchema)
def return_task():
    data = request.validated_data
    task_id = data.task_id
    user_id = get_jwt_identity()

    # security check
    if not check_task_auth(user_id, task_id):
        return HttpResponse.error('Illegal state or role, please DO NOT try to HACK the system.')

    task_info = Task_model.query.filter_by(task_id=task_id).first()
    print(task_info)
    if not task_info:
        return HttpResponse.error("Task not found.")

    if task_info.task_status == 'queued':
        return HttpResponse.ok("Task is queued.")

    if task_info.task_status == 'error':
        # 从task_dir中读取error.log,返回给前端
        try:
            with open(f'{task_info.task_dir}/error.log', 'r') as f:
                error_info = f.read()
            return _my_response(200, "Task error", error_info=error_info)
        except Exception as e:
            with open(f'{task_info.task_dir}/error.log', 'r') as f:
                error_info = str(e)
            return HttpResponse.ok("Task error", error_info=error_info)
    task_res = task_info.to_detail_dict()
    return HttpResponse.ok("Task info found.", task_res=task_res)
