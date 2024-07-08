from typing import Optional
from flask import Blueprint, request, jsonify
import uuid
from datetime import datetime

from app.config import DDLTIME
from app.model.User_model import User_model
from app.model.Task_model import Task_model
from app.vo.response import myResponse

from app.jobs.cctraing_job import enqueue_cc_task

# from .utils.py import get_available_port
import time
# from app.views.config import get_config_yaml, set_config_yaml, get_config_json, set_config_json

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
    task_id = uuid.uuid1()
    task = Task_model(task_id=task_id, user_id=user_id, task_status='queued', running_port=0, task_score=0,
                      created_time=now.strftime("%Y-%m-%d-%H-%M-%S"), cname=cname, task_dir=temp_dir,
                      algorithm=filename[:-3])

    # task = executor.submit(run_task, newfilename[:-3])
    # task = run_task.queue()
    # update_task_status(task_id, 'queued')
    task.save()
    enqueue_cc_task(task)
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

# @rq.job(timeout='1h')
# def run_task(filenames, task_id, temp_dir):
#     # # config yaml
#     # r = lambda: random.randint(0, 255)
#     # random_color = '#%02X%02X%02X' % (r(), r(), r())
#     # print("test redis query")
#     # c_content = get_config_yaml()
#     # print("yaml config: {}, type: {}".format(c_content, type(c_content)))
#     # if filename not in c_content['schemes'].keys():
#     #     c_content['schemes'][filename] = {'name': filename, 'color': random_color, 'marker': '*'}
#     # set_config_yaml(c_content)
#     # # set scheme name
#     # jsoncontent = get_config_json()
#     # if filename not in jsoncontent.get("cc_schemes"):
#     #     jsoncontent["cc_schemes"].append(filename)
#     # set_config_json(jsoncontent)
#     test_port = get_available_port()
#     print("select port {} for running {}".format(test_port, task_id))
#     Task_model.query.get(task_id).update(running_port=test_port, task_status='running')
#     #receive_port = test_port
#     # signal.signal(signal.SIGPIPE, signal.SIG_DFL)
#     # update_task_status(task_id, 'running')
#     cmd = 'bash ./run_job.sh ' + path_remake(filenames) + ' ' + str(test_port) + ' ' + str(task_id) + ' ' + str(
#         temp_dir) + ' 2>&1 | tee /home/liuwei/Transhub_data/cc_training/log/' + str(
#         task_id) + '_logfile.txt; python /home/liuwei/pantheon/src/analysis/plot.py'
#     os.system(cmd)


# Add other task related routes
