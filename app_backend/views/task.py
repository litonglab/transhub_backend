import os
import re
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
from app_backend.validators.schemas import TaskInfoSchema
from app_backend.vo.response import myResponse

task_bp = Blueprint('task', __name__)


def check_illegal(file) -> bool:
    dangerous_functions = [
        # 文件系统操作
        "fopen", "open", "creat", "remove", "unlink", "rename",
        "mkdir", "rmdir", "chmod", "chown", "symlink", "link",
        # 进程/系统命令
        "system", "execve", "execv", "execl", "execle", "execlp",
        "execvp", "execvpe", "popen", "fork", "vfork",
        # 动态代码加载
        "dlopen", "dlsym", "dlclose", "dlerror",
        # 网络操作
        # "socket", "connect", "bind", "listen", "accept",
        # "send", "sendto", "recv", "recvfrom",
        # 内存/指针操作 (可能用于漏洞利用)
        # "gets", "strcpy", "strcat", "sprintf", "vsprintf",
        # "scanf", "sscanf",
        # "malloc", "free",  # 需结合上下文分析
        # 系统资源操作
        "ioctl", "syscall",  # 直接系统调用
        "mmap", "munmap", "mprotect",  # 内存映射
        # 环境/权限相关
        "setuid", "setgid", "seteuid", "setegid",
        "putenv", "clearenv", "getenv",
        # 信号处理 (可能干扰沙箱)
        "signal", "sigaction", "raise",
        # Windows API (如果跨平台需检测)
        "WinExec", "CreateProcess", "ShellExecute",
        # 多线程相关
        "pthread_create",
        # 其他危险函数
        "abort", "exit", "_exit"  # 可能用于强制终止监控进程
    ]
    code = file.stream.read().decode(errors='ignore')
    for func in dangerous_functions:
        if re.search(rf'\b{func}\s*\(', code):
            return False
    return True


@task_bp.route("/task_upload", methods=["POST"])
@jwt_required()
def upload_project_file():
    ddl_time = time.mktime(time.strptime(DDLTIME, "%Y-%m-%d-%H-%M-%S"))
    if time.time() > ddl_time:
        return myResponse(400, "The competition has ended.")

    file = request.files.get('file')
    user_id = get_jwt_identity()  # 用户id
    # 从token中获取cname
    cname = get_jwt().get('cname')
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
    return myResponse(200, "Upload Success. Task is running.", filename=filename, tasks=task_ids)


@task_bp.route("/task_get_task_info", methods=["POST"])
@jwt_required()
@validate_request(TaskInfoSchema)
def return_task():
    data = request.validated_data
    task_id = data.task_id
    user_id = get_jwt_identity()

    # security check
    if not check_task_auth(user_id, task_id):
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
