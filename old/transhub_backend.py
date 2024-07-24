# coding=utf-8
import datetime
import json
import os
import PyPDF2
import random
import threading
import time
import yaml
import uuid

from flask_cors import CORS
from flask_redis import FlaskRedis
from flask import Flask, request, send_from_directory, make_response, jsonify, send_file
from flask_rq2 import RQ
from concurrent.futures import ThreadPoolExecutor 

from old.check_login import *

executor = ThreadPoolExecutor(8)
app = Flask(__name__)
CORS(app,supports_credentials=True, origins='*')
rq=RQ(app)
redis_client = FlaskRedis(app)

mutex = threading.Lock()









#  app_backend/views/utils.py
def path_remake(path):
    return path.replace(' ', '\ ').replace('(', '\(').replace(')', '\)').replace('&', '\&')

# app_backend/views/utils.py
def get_available_port():
    pscmd = "netstat -nul |grep -v Active| grep -v Proto|awk '{print $4}'|awk -F: '{print $NF}'"  # 定义netstat命令的字符串
    tt= random.randint(20000,50000)
    while tt:
        mutex.acquire()
        procs = os.popen(pscmd).read()  # 执行netstat命令并获取输出结果
        mutex.release()
        procarr = procs.split("\n")  # 将输出结果按行分割成列表
        if str(tt) not in procarr:
            return str(tt)
        else:
            tt= random.randint(20000,50000)

def create_table():
    create_user_table()
    create_task_table()
    print('table created')

YAML_KEY = "yaml_config"
JSON_KEY = "json_config"

ALL_CLASS = ["计算机系统基础II", "计算机网络", "校内赛计算机网络赛道"]
ALL_SUMMARY_DIR = ["/home/liuwei/Transhub_data/pantheon-ics",
                   "/home/liuwei/Transhub_data/pantheon-network",
                   "/home/liuwei/Transhub_data/pantheon-competition",
                   "/home/liuwei/pantheon"] # default

# @app_backend.route("/")
# def index():
#     return redirect(url_for('user_login'))

#  app_backend/views/user.py
@app.route('/user_login',methods=['POST'])
def user_login():
    request_data = request.json or request.form
    username = request_data['username']
    password = request_data['password']
    if is_null(username, password):
        login_massage = "温馨提示：账号密码是必填"
        return {"code": 400, "message": login_massage}
    elif is_existed(username, password):
        user_id = query_user(username, password)
        return {"code": 200, "message": "登录成功！", "user_id": user_id}
    elif exist_user(username):
        login_massage = "温馨提示：密码错误，请输入正确密码"
        return {"code": 400, "message": login_massage}
    else:
        login_massage = "温馨提示：用户尚未注册，请点击注册"
        return {"code": 400, "message": login_massage}

#  app_backend/views/user.py
@app.route('/user_register',methods=['POST'])
def user_register():
    try:
        request_data = request.json or request.form
        username = request_data['username']
        password = request_data['password']
        real_name = request_data['real_name']
        sno = request_data['sno']
        Sclass = request_data['Sclass']
        user_id = uuid.uuid1()
        if exist_user(username):
            message = "该用户名已被占用！"
            return {"code": 400, "message": message}
        elif is_null_info(real_name, sno, Sclass):
            message = "温馨提示：真实信息是必填"
            return {"code": 400, "message": message}
        elif not str(sno).isdecimal() or len(sno) != 10:
            message = "温馨提示：请输入10位数字学号"
            return {"code": 400, "message": message}
        else:
            insert_user_item(user_id, username,password,'0',real_name,Sclass,sno)
            message = "注册成功！请返回登录页面"
            return {"code": 200, "message": message, "user_id": user_id}
    except Exception as e:
        print("register occur error: {}".format(e))
        return {"code": 500, "message": "Register occur ERROR!"}

#  app_backend/views/user.py
@app.route("/change_password",methods=['POST'])
def change_password():
    request_data = request.json or request.form
    user_id = request_data['user_id']
    new_pwd = request_data['new_pwd']
    change_user_item(user_id, new_pwd)
    message = "修改密码成功！"
    return {"code": 200, "message": message}

#  app_backend/views/task.py
@app.route("/upload",methods=["POST"])
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
        return {"code": 400, "message": "Your algorithm is not in compliance with standards. Please name it according to variable naming conventions."}
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

# app_backend/views/help.py
@app.route("/get_help/cca_guide", methods=["GET"])
def return_cca_file():
    return send_from_directory("/home/liuwei/Transhub/help/", 'cca_guide.docx', as_attachment=True)

# app_backend/views/help.py
@app.route("/get_help/user_guide", methods=["GET"])
def return_guide_file():
    return send_from_directory("/home/liuwei/Transhub/help/", 'user_guide.docx', as_attachment=True)

# app_backend/views/summary.py
@app.route("/get_ranks",methods=["GET"])
def return_ranks():
    user_id = request.args.get("user_id")
    if not user_id:
        return {"code": 400, "message": "Bad request!"}
    real_info = query_real_info(user_id)
    if real_info[1] in ALL_CLASS:
        rank_list = query_rank_list(real_info[1])
    else:
        rank_list = query_rank_list()
    if not rank_list:
        return jsonify({"code": 500, "message": "Maybe no task has finished, you can rerun your code to generate it."})
    # task_res = {"task_id": task_info[0], "user_id": task_info[1], "task_status": task_info[2], "task_score": task_info[3], "running_port": task_info[4]}
    ranks_info = [{"task_id": rank[0], "user_id": rank[1], "username": rank[2], "cca_name": rank[3], "task_score": rank[4], "created_time": rank[5], "score_without_loss": rank[6], "score_with_loss": rank[7]} for rank in rank_list]
    if request.args and request.args.get("order") == "asc":
        ranks_info = [{"task_id": rank[0], "user_id": rank[1], "username": rank[2], "cca_name": rank[3], "task_score": rank[4], "created_time": rank[5], "score_without_loss": rank[6], "score_with_loss": rank[7]} for rank in reversed(rank_list)]
    return jsonify({"code": 200, "rank_list": ranks_info})


# app_backend/views/history.py
@app.route("/get_history_records/<user_id>",methods=["GET"])
def return_history_records(user_id):
    history_records = query_history_records(user_id)
    if not history_records:
        return jsonify({"code": 500, "message": "Maybe you never submit a record, you can submit your code now!"})
    history_info = [{"task_id": record[0], "user_id": record[1], "task_status": record[2], "task_score": record[3], "running_port": record[4], "cca_name": record[5], "created_time": record[6], "score_without_loss": record[7], "score_with_loss": record[8]} for record in history_records]
    return jsonify({"code": 200, "history_records": history_info})

# app_backend/views/user.py
@app.route("/get_real_info/<user_id>",methods=["GET"])
def return_real_info(user_id):
    real_record = query_real_info(user_id)
    if not real_record:
        return jsonify({"code": 500, "message": "Error in query real info!"})
    print(real_record)
    real_info = {"real_name":real_record[0], "myclass":real_record[1], "sno":real_record[2]}
    return jsonify({"code":200, "real_info":real_info})

# app_backend/views/user.py
@app.route("/set_real_info/<user_id>",methods=["GET"])
def change_real_info(user_id):
    new_real_record = request.args
    if not new_real_record:
        return jsonify({"code": 400, "message": "Real info need to be provided!"})
    if not new_real_record.get("real_name") or not new_real_record.get("myclass") or not new_real_record.get("sno"):
        return jsonify({"code": 400, "message": "Real info is not complete!"})
    if not str(new_real_record.get("sno")).isdecimal() or len(new_real_record.get("sno")) != 10:
        message = "Please input correct student number(ten numbers)!"
        return {"code": 400, "message": message}
    update_real_info(user_id, new_real_record.get("real_name"), new_real_record.get("myclass"), new_real_record.get("sno"))
    return jsonify({"code":200, "message": "Update real info success."})

# app_backend/views/source_code.py
@app.route("/get_source_code/<task_id>",methods=["GET"])
def return_code(task_id):
    task_info = query_task(task_id)
    print(task_info)
    if not task_info or len(task_info)<7:
        return jsonify({"code": 500, "message": "Maybe task {} is not running, you can rerun your code to generate it.".format(task_id)})
    cca_name = task_info[5] or ''
    result_directory = "/home/liuwei/Transhub_data/cc_training/{}/sourdough/datagrump/result/".format(task_id)
    if os.path.exists(result_directory+cca_name+'.cc'):
        directory = result_directory
    else:
        # no finished normally
        directory = "/home/liuwei/Transhub_data/cc_training/{}/sourdough/datagrump/".format(task_id)
        cca_name = "controller"
    try:
        response = make_response(
                send_from_directory(directory, cca_name+'.cc', as_attachment=True))
        return response
    except Exception as e:
        return jsonify({"code": 404, "message": "{}".format(e)})

# app_backend/views/log.py
@app.route("/get_log/<task_id>",methods=["GET"])
def return_log(task_id):
    task_info = query_task(task_id)
    if not task_info:
        return jsonify({"code": 500, "message": "Maybe task {} is not running, you can rerun your code to generate it.".format(task_id)})
    cca_name = task_info[5]
    log_name = task_id+'_throughput.txt'
    result_directory = "/home/liuwei/Transhub_data/cc_training/{}/sourdough/datagrump/result/".format(task_id)
    if os.path.exists(result_directory+task_id+'_throughput.txt'):
        directory = result_directory
    else:
        # no finished normally
        directory = "/home/liuwei/Transhub_data/cc_training/log/"
        log_name = "{}_logfile.txt".format(cca_name)
    try:
        response = make_response(
                send_from_directory(directory, log_name, as_attachment=True))
        return response
    except Exception as e:
        return jsonify({"code": 404, "message": "{}".format(e)})

# app_backend/views/task.py
@app.route("/get_task_info/<task_id>",methods=["GET"])
def return_task(task_id):
    task_info = query_task(task_id)
    if not task_info:
        return jsonify({"code": 500, "message": "Maybe task {} is not running, you can rerun your code to generate it.".format(task_id)})
    task_res = {"task_id": task_info[0], "user_id": task_info[1], "task_status": task_info[2], "task_score": task_info[3], "running_port": task_info[4], "cca_name": task_info[5], "score_without_loss": task_info[6], "score_with_loss": task_info[7]}
    return jsonify({"code": 200, "task_info": task_res})

# app_backend/views/user.py
@app.route("/get_old_pwd/<user_id>",methods=["GET"])
def return_old_pwd(user_id):
    old_pwd = query_pwd(user_id)
    if not old_pwd:
        return jsonify({"code": 500, "message": "Error in query old password!"})
    data = old_pwd[0]
    return jsonify({"code": 200, "data": data})

# app_backend/views/graph.py
@app.route("/get_loss_throughput_graph/<task_id>",methods=["GET"])
def return_loss_throughput_graph(task_id):
    directory = "/home/liuwei/Transhub_data/cc_training/{}/sourdough/datagrump/result/".format(task_id)
    try:
        response = send_file(directory+"throughput_loss_trace.png", cache_timeout=0, as_attachment=True)
        return response
    except Exception as e:
        return jsonify({"code": 500, "message": "{} Maybe you algorithm is still running or its result was wrong. You can rerun your code to generate graph.".format(e)})

# app_backend/views/graph.py
@app.route("/get_loss_delay_graph/<task_id>",methods=["GET"])
def return_loss_delay_graph(task_id):
    directory = "/home/liuwei/Transhub_data/cc_training/{}/sourdough/datagrump/result/".format(task_id)
    try:
        response = send_file(directory+"delay_loss_trace.png", cache_timeout=0, as_attachment=True)
        return response
    except Exception as e:
        return jsonify({"code": 500, "message": "{} Maybe you algorithm is still running or its result was wrong. You can rerun your code to generate graph.".format(e)})

# app_backend/views/graph.py
@app.route("/get_throughput_graph/<task_id>",methods=["GET"])
def return_throughput_graph(task_id):
    directory = "/home/liuwei/Transhub_data/cc_training/{}/sourdough/datagrump/result/".format(task_id)
    try:
        response = send_file(directory+"throughput.png", cache_timeout=0, as_attachment=True)
        return response
    except Exception as e:
        return jsonify({"code": 500, "message": "{} Maybe you algorithm is still running or its result was wrong. You can rerun your code to generate graph.".format(e)})


# app_backend/views/graph.py
@app.route("/get_delay_graph/<task_id>",methods=["GET"])
def return_delay_graph(task_id):
    directory = "/home/liuwei/Transhub_data/cc_training/{}/sourdough/datagrump/result/".format(task_id)
    try:
        response = send_file(directory+"delay.png", cache_timeout=0, as_attachment=True)
        return response
    except Exception as e:
        return jsonify({"code": 500, "message": "{} Maybe you algorithm is still running or its result was wrong. You can rerun your code to generate graph.".format(e)})

# app_backend/views/summary.py
@app.route("/get_loss_summary_svg", methods=["GET"])
def return_loss_summary_svg():
    return send_file("/home/liuwei/pantheon/src/experiments/data_p/pantheon_summary.svg", cache_timeout=0, as_attachment=True)

# app_backend/views/summary.py
@app.route("/get_loss_summary_pdf", methods=["GET"])
def return_loss_summary():
    return send_file("/home/liuwei/pantheon/src/experiments/data_p/pantheon_summary.pdf", cache_timeout=0, as_attachment=True)

# app_backend/views/help.py
@app.route("/get_zhinan", methods=["GET"])
def return_zhinan():
    return send_file("/home/liuwei/zhinan.pdf", cache_timeout=0, as_attachment=True)

# app_backend/views/summary.py
@app.route("/get_summary_svg", methods=["GET"])
def return_summary_svg():
    return send_file("/home/liuwei/pantheon/src/experiments/data/pantheon_summary.svg", cache_timeout=0, as_attachment=True)


# app_backend/views/summary.py
@app.route("/get_summary_pdf/<user_id>", methods=["GET"])
def return_summary(user_id):
    if not user_id:
        return {"code": 400, "message": "Bad request!"}
    real_info = query_real_info(user_id)
    if not real_info:
        return {"code": 400, "message": "Real info need be completed!"}
    temp_class = real_info[1]
    if temp_class == ALL_CLASS[0]:
        temp_dir = ALL_SUMMARY_DIR[0]
    elif temp_class == ALL_CLASS[1]:
        temp_dir = ALL_SUMMARY_DIR[1]
    else:
        temp_dir = ALL_SUMMARY_DIR[2]
    print(temp_dir)
    pdf_filenames = [f"{temp_dir}/src/experiments/data/pantheon_summary.pdf", f"{temp_dir}/src/experiments/data_p/pantheon_summary.pdf"]
    merger = PyPDF2.PdfMerger()
    for pdf_filename in pdf_filenames:
        merger.append(PyPDF2.PdfReader(pdf_filename))
    merger.write(f"{temp_dir}/merged_summary.pdf")
    return send_file(f"{temp_dir}/merged_summary.pdf", cache_timeout=0, as_attachment=True)

# app_backend/views/config.py
def set_config_yaml(config_content):
    p = redis_client.pipeline()
    p.set(YAML_KEY, str(config_content))
    p.execute()
    for temp_dir in ALL_SUMMARY_DIR:
        with open(f"{temp_dir}/src/config.yml", "w") as f:
            yaml.dump(config_content, f, default_flow_style=False)

# app_backend/views/config.py
def get_config_yaml():
    data = redis_client.get(YAML_KEY)
    if data:
        return yaml.safe_load(data)
    for temp_dir in ALL_SUMMARY_DIR:
        with open(f"{temp_dir}/src/config.yml", "r+") as f:
            c_content = yaml.safe_load(f)
            set_config_yaml(c_content)
            return c_content

# app_backend/views/config.py
def set_config_json(json_content):
    p = redis_client.pipeline()
    p.set(JSON_KEY, json.dumps(json_content))
    p.execute()
    for temp_dir in ALL_SUMMARY_DIR:
        with open(f"{temp_dir}/src/experiments/data/pantheon_metadata.json", "w") as f:
            print(f"write json to {temp_dir}/src/experiments/data/pantheon_metadata.json")
            json.dump(json_content, f, indent=4)
        with open(f"{temp_dir}/src/experiments/data_p/pantheon_metadata.json", "w") as f:
            print(f"write json to {temp_dir}/src/experiments/data_p/pantheon_metadata.json")
            json.dump(json_content, f, indent=4)

# app_backend/views/config.py
def get_config_json():
    data = redis_client.get(JSON_KEY)
    if data:
        return json.loads(data)
    for temp_dir in ALL_SUMMARY_DIR:
        with open(f"{temp_dir}/src/experiments/data/pantheon_metadata.json", "r") as f:
            jsoncontent = json.load(f)
            set_config_json(jsoncontent)
            return jsoncontent

# app_backend/views/task.py
@rq.job(timeout='1h')
def run_task(arg1, task_id, temp_dir):
    # config yaml
    r = lambda: random.randint(0, 255)
    random_color = '#%02X%02X%02X'%(r(), r(), r())
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
    #signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    update_task_status(task_id, 'running')
    cmd = 'bash ./run_job.sh '+path_remake(arg1) + ' ' + str(receive_port) + ' ' + str(task_id) +  ' ' + str(temp_dir) + ' 2>&1 | tee /home/liuwei/Transhub_data/cc_training/log/' + str(task_id) +'_logfile.txt; python /home/liuwei/pantheon/src/analysis/plot.py'
    os.system(cmd)

# run.py
def begin_work():
    worker = rq.get_worker()
    worker.work()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=54321, debug=True)
    app.config['RQ_REDIS_URL'] = 'redis://localhost:6379/0'
    scheduler = rq.get_scheduler(interval=5)
    scheduler.run()
    executor.submit(begin_work)

