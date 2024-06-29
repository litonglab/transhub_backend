import os
import random

from flask import Blueprint, request, jsonify
import uuid
from datetime import datetime

from app.config import ALL_SUMMARY_DIR, ALL_CLASS,USER_DIR_PREFIX
from app.model.User_model import *

from app.utils import get_available_port, path_remake
from app.model.Task_model import insert_task_item, update_task_status, query_task
# from .utils.py import get_available_port
import time
from app.views.config import get_config_yaml, set_config_yaml, get_config_json, set_config_json

task_bp = Blueprint('task', __name__)

def save_file_to_user_dir(user_id,task_id,file):
    user = query_user_by_id(user_id)
    user_dir = USER_DIR_PREFIX+user.get_user_dir()
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)




@task_bp.route("/upload", methods=["POST"])
def save_file():
    request_data = request.json or request.form
    if not request_data:
        return {"code": 400, "message": "No body params, please login firstly."}
    if not request_data.get('user_id'):
        return {"code": 400, "message": "No valid user_id, please login firstly."}

    user_id = request_data['user_id']
    task_id = uuid.uuid1()
    now = datetime.datetime.now()

    insert_task_item(task_id, user_id, 'init', now.strftime("%Y-%m-%d %H:%M:%S"))
    file = request.files.get('file')
    if file is None:
        file = request.files.get('uploadFile')
        print("file received from uploadfile")

    if file is None:
        update_task_status(task_id, "ERROR")
        return {"code": 400, "message": "文件上传失败"}

    filename = file.filename
    if filename[-3:] != ".cc" and filename[-2:] != ".c":
        update_task_status(task_id, "ERROR")
        return {"code": 400, "message": "File should be c program or c++ program!"}

    newfilename = ''.join(filename.split('.')[:-1]) + '.cc'

    if not newfilename[:-3].isidentifier():
        return {"code": 400, "message": "Your algorithm is not in compliance with standards. Please name it according "
                                        "to variable naming conventions."}
    if filename == 'log.cc':
        update_task_status(task_id, "ERROR")
        return {"code": 400, "message": "Name should not equals 'log'"}


    file.save("/home/liuwei/Transhub_data/received/{}".format(newfilename))
    file_path = "/home/liuwei/Transhub_data/received/{}".format(newfilename)

    with open(file_path, 'r') as f:
        for line in f.readlines():
            if 'fstream' in line:
                return {"code": 400, "message": "Illegal Operation!"}
            elif 'fopen' in line:
                return {"code": 400, "message": "Illegal Operation!"}
            elif 'open' in line:
                return {"code": 400, "message": "Illegal Operation!"}
    real_info = query_real_info(user_id)
    if not real_info:
        return {"code": 400, "message": "Real info need be completed!"}
    temp_class = real_info[1]
    if temp_class == ALL_CLASS[0]:
        temp_dir = ALL_SUMMARY_DIR[0]
        ddl_time = time.mktime(time.strptime('2024-06-19 23:01:00', '%Y-%m-%d %H:%M:%S'))
        if time.time() > ddl_time:
            update_task_status(task_id, "ERROR")
            return {"code": 405, "message": "Sorry, the deadline has passed. You can no longer submit your code.!"}
    elif temp_class == ALL_CLASS[1]:
        temp_dir = ALL_SUMMARY_DIR[1]
        ddl_time = time.mktime(time.strptime('2024-06-16 23:01:00', '%Y-%m-%d %H:%M:%S'))
        if time.time() > ddl_time:
            update_task_status(task_id, "ERROR")
            return {"code": 405, "message": "Sorry, the deadline has passed. You can no longer submit your code.!"}
    elif temp_class == ALL_CLASS[2]:
        temp_dir = ALL_SUMMARY_DIR[2]
        ddl_time = time.mktime(time.strptime('2024-05-23 17:32:00', '%Y-%m-%d %H:%M:%S'))
        if time.time() > ddl_time:
            update_task_status(task_id, "ERROR")
            return {"code": 405, "message": "Sorry, the deadline has passed. You can no longer submit your code.!"}
    else:
        temp_dir = ALL_SUMMARY_DIR[-1]
    # task = executor.submit(run_task, newfilename[:-3])
    task = run_task.queue(newfilename[:-3], task_id, temp_dir)
    update_task_status(task_id, 'queued')
    return {"code": 200, "message": "Upload Success. Task is running.", "filename": newfilename, "task_id": task_id}


@task_bp.route("/get_task_info/<task_id>", methods=["GET"])
def return_task(task_id):
    task_info = query_task(task_id)
    if not task_info:
        return jsonify({"code": 500,
                        "message": "Maybe task {} is not running, you can rerun your code to generate it.".format(
                            task_id)})
    task_res = {"task_id": task_info[0], "user_id": task_info[1], "task_status": task_info[2],
                "task_score": task_info[3], "running_port": task_info[4], "cca_name": task_info[5],
                "score_without_loss": task_info[6], "score_with_loss": task_info[7]}
    return jsonify({"code": 200, "task_info": task_res})


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
    update_task_status(task_id, 'running')
    cmd = 'bash ./run_job.sh ' + path_remake(arg1) + ' ' + str(receive_port) + ' ' + str(task_id) + ' ' + str(
        temp_dir) + ' 2>&1 | tee /home/liuwei/Transhub_data/cc_training/log/' + str(
        task_id) + '_logfile.txt; python /home/liuwei/pantheon/src/analysis/plot.py'
    os.system(cmd)

# Add other task related routes
