import os
import random
from typing import Optional
from flask import Blueprint, request, jsonify
import uuid
from datetime import datetime

from app import rq
from app.config import ALL_SUMMARY_DIR_PATH, ALL_CLASS, USER_DIR_PATH, DDLTIME, BASEDIR
from app.model.User_model import User_model
from app.model.Task_model import Task_model
from app.vo.response import myResponse

from app.utils import get_available_port, path_remake

# from .utils.py import get_available_port
import time
from app.views.config import get_config_yaml, set_config_yaml, get_config_json, set_config_json

from app.security.safe_check import check_user_state, check_task_auth

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


def save_file_to_user_dir(user_id, file, cname, nowtime):
    user = User_model.query.get(user_id)
    user_dir = user.get_user_dir(cname)
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)
    # 由当前时间生成文件夹
    filedir = user_dir + "/" + nowtime
    if not os.path.exists(filedir):
        os.makedirs(filedir)
    file.save(filedir + "/" + file.filename)


@task_bp.route("/upload", methods=["POST"])
def upload_project_file():
    request_data = request.json or request.form
    if not request_data:
        return myResponse(400, "No body params, please login firstly.")
    if not request_data.get('user_id'):
        return myResponse(400, "Please login firstly.")

    user_id = request_data['user_id']  # 用户id
    cname = request_data['cid']  # 参赛的比赛名称
    task_id = uuid.uuid1()

    now = datetime.datetime.now()

    # insert_task_item(task_id, user_id, 'init', now.strftime("%Y-%m-%d %H:%M:%S"))
    task = Task_model(task_id=task_id, user_id=user_id, task_status='init',
                      created_time=now.strftime("%Y-%m-%d %H:%M:%S"))
    task.save()

    # security check
    if not (check_user_state(user_id)) or (not check_task_auth(user_id, task_id)):
        return myResponse(400, 'Illegal state or role, please DO NOT try to HACK the system.')

    file = request.files.get('file')
    if file is None:
        file = request.files.get('uploadFile')
        print("file received from uploadfile")

    if file is None:
        # update_task_status(task_id, "ERROR")
        task.update(task_status='ERROR')
        return myResponse(400, "No file received.")

    filename = file.filename
    if filename[-3:] != ".cc" and filename[-2:] != ".c":
        # update_task_status(task_id, "ERROR")
        task.update(task_status='ERROR')
        return myResponse(400, "File should be c program or c++ program!")

    if filename == 'log.cc':
        task.update(task_status='ERROR')
        return myResponse(400, "Illegal name:log.cc")

    save_file_to_user_dir(user_id, file, cname, now.strftime("%Y-%m-%d %H:%H:%S"))

    real_info = User_model.query.get(user_id)
    if not real_info:
        return myResponse(400, "User not found.")

    temp_dir = real_info.get_user_dir(cname) + "/" + now.strftime("%Y-%m-%d %H:%H:%S")
    ddl_time = time.mktime(time.strptime(DDLTIME, '%Y-%m-%d %H:%M:%S'))

    if time.time() > ddl_time:
        task.update(task_status='ERROR')
        return myResponse(400, "The competition has ended.")

    # task = executor.submit(run_task, newfilename[:-3])
    # task = run_task.queue(newfilename[:-3], task_id, temp_dir)
    # update_task_status(task_id, 'queued')

    # return {"code": 200, "message": "Upload Success. Task is running.", "filename": filename, "task_id": task_id}
    return myResponse(200, "Upload Success. Task is running.", filename=filename, task_id=task_id)


@task_bp.route("/get_task_info", methods=["POST"])
def return_task():

    task_id = request.json.get('task_id')
    user_id = request.json.get('user_id')
    # security check
    if not (check_user_state(user_id)) or (not check_task_auth(user_id, task_id)):
        return myResponse(400, 'Illegal state or role, please DO NOT try to HACK the system.')

    task_info: Optional[Task_model] = Task_model.query.get(task_id)

    if not task_info:
        return myResponse(400, "Task not found.")

    # task_res = {"task_id": task_info, "user_id": task_info[1], "task_status": task_info[2],
    #             "task_score": task_info[3], "running_port": task_info[4], "cca_name": task_info[5],
    #             "score_without_loss": task_info[6], "score_with_loss": task_info[7]}
    task_res = {"task_id": task_info.task_id, "user_id": task_info.user_id, "task_status": task_info.task_status,
                "task_score": task_info.task_score, "running_port": task_info.running_port}

    return myResponse(200, "Task info found.", task_res=task_res)


@rq.job(timeout='1h')
def run_task(arg1, task_id, temp_dir):
    # config yaml
    r = lambda: random.randint(0, 255)
    random_color = '#%02X%02X%02X' % (r(), r(), r())
    print("test redis query")
    c_content = get_config_yaml()
    print("yaml config: {}, type: {}".format(c_content, type(c_content)))
    if arg1 not in c_content['schemes'].keys():
        c_content['schemes'][arg1] = {'name': arg1, 'color': random_color, 'marker': '*'}
    set_config_yaml(c_content)
    # set scheme name
    jsoncontent = get_config_json()
    if arg1 not in jsoncontent.get("cc_schemes"):
        jsoncontent["cc_schemes"].append(arg1)
    set_config_json(jsoncontent)
    test_port = get_available_port()
    print("select port {} for running {}".format(test_port, task_id))
    receive_port = test_port
    # signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    # update_task_status(task_id, 'running')
    cmd = 'bash ./run_job.sh ' + path_remake(arg1) + ' ' + str(receive_port) + ' ' + str(task_id) + ' ' + str(
        temp_dir) + ' 2>&1 | tee /home/liuwei/Transhub_data/cc_training/log/' + str(
        task_id) + '_logfile.txt; python /home/liuwei/pantheon/src/analysis/plot.py'
    os.system(cmd)

# Add other task related routes
