from flask import Blueprint, request
import uuid
from datetime import datetime

from app_backend.config import DDLTIME
from app_backend.model.User_model import User_model
from app_backend.model.Task_model import Task_model
from app_backend.vo.response import myResponse

from app_backend.jobs.cctraing_job import enqueue_cc_task

# from .utils.py import get_available_port
import time
# from app_backend.views.config import get_config_yaml, set_config_yaml, get_config_json, set_config_json

from app_backend.security.safe_check import check_user_state, check_task_auth

task_bp = Blueprint('task', __name__)


def check_illegal(file) -> (bool, dict):
    for line in file.stream.readlines():
        if 'fstream' in line:
            return False, {"code": 400, "message": "Illegal Operation!"}
        elif 'fopen' in line:
            return False, {"code": 400, "message": "Illegal Operation!"}
        elif 'open' in line:
            return False, {"code": 400, "message": "Illegal Operation!"}
    return True, {}


@task_bp.route("/upload", methods=["POST"])
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

    if file is None:
        return myResponse(400, "No file received.")

    filename = file.filename
    if filename[-3:] != ".cc" and filename[-2:] != ".c":
        return myResponse(400, "File should be c program or c++ program!")

    if filename == 'log.cc':
        return myResponse(400, "Illegal name:log.cc")

    # security check
    if not check_user_state(user_id):
        return myResponse(400, 'Illegal state or role, please DO NOT try to HACK the system.')

    user = User_model.query.get(user_id)
    if not user:
        return myResponse(400, "User not found.")
    now = datetime.now()
    user.save_file_to_user_dir(file, cname, now.strftime("%Y-%m-%d-%H-%M-%S"))
    temp_dir = user.get_user_dir(cname) + "/" + now.strftime("%Y-%m-%d-%H-%M-%S")

    # 构建task
    task_id = str(uuid.uuid1())
    task = Task_model(task_id=task_id, user_id=user_id, task_status='queued', running_port=0, task_score=0,
                      created_time=now.strftime("%Y-%m-%d-%H-%M-%S"), cname=cname, task_dir=temp_dir,
                      algorithm=filename[:-3])

    # task = executor.submit(run_task, newfilename[:-3])
    # task = run_task.queue()
    # update_task_status(task_id, 'queued')
    task.save()
    enqueue_cc_task(task_id)
    # return {"code": 200, "message": "Upload Success. Task is running.", "filename": filename, "task_id": task_id}
    return myResponse(200, "Upload Success. Task is running.", filename=filename, task_id=task_id)


@task_bp.route("/get_task_info", methods=["POST"])
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
