import os
import random

import threading
from app.config import USER_DIR_PATH

mutex = threading.Lock()


def path_remake(path):
    return path.replace(' ', '\ ').replace('(', '\(').replace(')', '\)').replace('&', '\&')


def get_available_port():
    pscmd = "netstat -nul |grep -v Active| grep -v Proto|awk '{print $4}'|awk -F: '{print $NF}'"  # 定义netstat命令的字符串
    tt = random.randint(20000, 50000)
    while tt:
        mutex.acquire()
        procs = os.popen(pscmd).read()  # 执行netstat命令并获取输出结果
        mutex.release()
        procarr = procs.split("\n")  # 将输出结果按行分割成列表
        if str(tt) not in procarr:
            return str(tt)
        else:
            tt = random.randint(20000, 50000)
