import os

from flask import Blueprint, request
import uuid
from datetime import datetime

from app_backend.config import DDLTIME
from app_backend.model.User_model import User_model
from app_backend.model.Task_model import Task_model
from app_backend.vo.response import myResponse

from app_backend.jobs.cctraining_job import enqueue_cc_task

import time
from app_backend.config import get_config_by_cname

from app_backend.security.safe_check import check_user_state, check_task_auth

task_bp = Blueprint('task', __name__)


def check_illegal(file) -> (bool, dict):
    content = file.stream.read().decode(errors='ignore')
    if 'fstream' in content or 'fopen' in content or 'open' in content:
        return False
    return True


@task_bp.route("/task_upload", methods=["POST"])
def upload_project_file():
    ddl_time = time.mktime(time.strptime(DDLTIME, "%Y-%m-%d-%H-%M-%S"))
    if time.time() > ddl_time:
        return myResponse(400, "The competition has ended.")

    request_data = request.form
    if not request_data:
        return myResponse(400, "No body params, please login firstly.")
    if not request_data.get('user_id'):
        return myResponse(400, "Please login firstly.")

    file = request.files.get('file')
    user_id = request_data['user_id']  # 用户id
    cname = request_data['cname']  # 参赛的比赛名称
    config = get_config_by_cname(cname)
    if not config:
        return myResponse(400, "No such competition.")
    if file is None:
        return myResponse(400, "No file received.")

    filename = file.filename
    if filename[-3:] != ".cc" and filename[-2:] != ".c":
        return myResponse(400, "File should be c program or c++ program!")

    if filename == 'log.cc':
        return myResponse(400, "Illegal name:log.cc")

    # 检查代码是否合法
    is_legal = check_illegal(file)
    if not is_legal:
        return myResponse(400, '文件存在高危操作，请删除后重新上传')
    file.stream.seek(0)  # 检查后重置文件流指针

    # security check
    if not check_user_state(user_id):
        return myResponse(400, 'Illegal state or role, please DO NOT try to HACK the system.')

    user = User_model.query.get(user_id)
    if not user:
        return myResponse(400, "User not found.")
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
                                  created_time=now.strftime("%Y-%m-%d-%H-%M-%S"), cname=cname, task_dir=temp_dir+"/" + trace_name+"_"+str(loss)+"_"+str(buffer_size),
                                  algorithm=filename[:-3], trace_name=trace_name, upload_id=upload_id, loss_rate=loss,buffer_size=buffer_size)

                # task = executor.submit(run_task, newfilename[:-3])
                # task = run_task.queue()
                # update_task_status(task_id, 'queued')
                task.save()
                task_ids.append(task_id)
                enqueue_cc_task(task_id)
    # return {"code": 200, "message": "Upload Success. Task is running.", "filename": filename, "task_id": task_id}
    return myResponse(200, "Upload Success. Task is running.", filename=filename, tasks=task_ids)


@task_bp.route("/task_get_task_info", methods=["POST"])
def return_task():
    task_id = request.json.get('task_id')
    user_id = request.json.get('user_id')
    # security check
    if not (check_user_state(user_id)) or (not check_task_auth(user_id, task_id)):
        return myResponse(400, 'Illegal state or role, please DO NOT try to HACK the system.')

    task_info = Task_model.query.filter_by(task_id=task_id).first()
    print(task_info)
    if not task_info:
        return myResponse(400, "Task not found.")

    if task_info.task_status == 'queued':
        return myResponse(200, "Task is queued.")

    if task_info.task_status == 'error':
        # 从task_dir中读取error.log,返回给前端
        try:
            with open(f'{task_info.task_dir}/error.log', 'r') as f:
                error_info = f.read()
            return myResponse(200, "Task error", error_info=error_info)
        except Exception as e:
            with open(f'{task_info.task_dir}/error.log', 'r') as f:
                error_info = str(e)
            return myResponse(200, "Task error", error_info=error_info)
    task_res = task_info.to_detail_dict()
    return myResponse(200, "Task info found.", task_res=task_res)
