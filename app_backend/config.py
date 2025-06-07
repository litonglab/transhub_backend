import os

# 以下配置由管理员填写
# ===admin config start.===
BASEDIR = "/Users/zjx/Documents/code/my/transhub_backend/project/Transhub_data"

ALL_CLASS = {
    "计算机系统基础II": {
        "name": "pantheon-ics",
        "allow_login": True,
        "start_time": "2024-09-01-00-00-00",
        "end_time": "2025-06-04-21-00-00",
        "loss_rate": [0.0],
        "buffer_size": [20, 250],
        # 以下字段由系统生成，无需填写
        # ===system generated start.===
        "path": "",  # 系统生成
        "zhinan_path": "",  # 系统生成
        "downlink_dir": "",  # 系统生成
        "uplink_dir": "",  # 系统生成
        "student_list": [],  # 系统生成
        # "cca_guide_path": "",  # 系统生成，此字段暂未使用
        # "user_guide_path": "",  # 系统生成，此字段暂未使用
        # ===system generated end.===
    },
    "计算机网络": {
        "name": "pantheon-network",
        "allow_login": True,
        "start_time": "2024-09-01-00-00-00",
        "end_time": "2025-06-02-21-00-00",
        "loss_rate": [0.0],
        "buffer_size": [20, 250],
        # 以下字段由系统生成，无需填写
        # ===system generated start.===
        "path": "",  # 系统生成
        "zhinan_path": "",  # 系统生成
        "downlink_dir": "",  # 系统生成
        "uplink_dir": "",  # 系统生成
        "student_list": [],  # 系统生成
        # "cca_guide_path": "",  # 系统生成，此字段暂未使用
        # "user_guide_path": "",  # 系统生成，此字段暂未使用
        # ===system generated end.===
    },
    "校内赛计算机网络赛道": {
        "name": "pantheon-competition",
        "allow_login": False,
        "start_time": "2024-09-01-00-00-00",
        "end_time": "2025-06-02-21-00-00",
        "loss_rate": [0.0],
        "buffer_size": [20, 250],
        # 以下字段由系统生成，无需填写
        # ===system generated start.===
        "path": "",  # 系统生成
        "zhinan_path": "",  # 系统生成
        "downlink_dir": "",  # 系统生成
        "uplink_dir": "",  # 系统生成
        "student_list": [],  # 系统生成
        # "cca_guide_path": "",  # 系统生成，此字段暂未使用
        # "user_guide_path": "",  # 系统生成，此字段暂未使用
        # ===system generated end.===
    }
}

LOG_CONFIG = {
    "LOG_DIR": os.path.join(BASEDIR, "logs"),  # 日志文件目录
    "LOG_LEVEL": "INFO",  # 日志级别
    "LOG_MAX_BYTES": 10 * 1024 * 1024,  # 单个日志文件最大大小（10MB）
    "LOG_BACKUP_COUNT": 5,  # 保留的日志文件数量
    "LOG_FILENAME": "app.log",  # 日志文件名
}

MYSQL_CONFIG = {
    "MYSQL_USERNAME": 'root',
    "MYSQL_PASSWORD": '123456',
    "MYSQL_ADDRESS": 'localhost:3306',
    "MYSQL_DBNAME": 'transhub_base',
}

REDIS_CONFIG = {
    "REDIS_ADDRESS": 'localhost',
    "REDIS_PORT": 6379,
    "REDIS_DB": 0,
}

JWT_CONFIG = {
    # JWT密钥，JWT密钥长度 ≥ 32字节
    # JWT密钥泄露会导致安全问题（可通过伪造token登录任意用户），请妥善保管。
    # 建议配置为None，自动生成一个随机密钥，避免泄露。
    "JWT_SECRET_KEY": None,  # JWT密钥，配置为None时会自动生成一个随机密钥
    "JWT_ACCESS_TOKEN_EXPIRES": 60 * 60 * 24 * 3,  # JWT访问令牌过期时间，单位为秒（3天）
}
# ===admin config end.===

# 以下配置由系统生成
# 由于循环导入，此模块不允许使用logger
# ===system generated start.===
CNAME_LIST = list(ALL_CLASS.keys())
USER_DIR_PATH = os.path.join(BASEDIR, "user_data")
REGISTER_STUDENT_LIST = set()


def fill_class_config():
    """
    Fill the config with paths based on the cname.
    """
    for cname, config in ALL_CLASS.items():
        config["path"] = os.path.join(BASEDIR, config["name"])
        config["zhinan_path"] = os.path.join(config["path"], 'help', 'zhinan.md')
        config["downlink_dir"] = os.path.join(config["path"], 'test_data', 'downlink')
        config["uplink_dir"] = os.path.join(config["path"], 'test_data', 'uplink')
        # config["cca_guide_path"] = config["path"] + "/help/cca_guide.docx"  # 暂未使用
        # config["user_guide_path"] = config["path"] + "/help/user_guide.docx"  # 暂未使用
        student_list_path = os.path.join(config["path"], 'student_list.txt')
        if os.path.exists(student_list_path):
            with open(student_list_path, 'r') as f:
                config["student_list"] = [line.strip() for line in f if line.strip()]
                # 将学生列表加到可注册学号列表集合中
                REGISTER_STUDENT_LIST.update(config["student_list"])


fill_class_config()
# ===system generated end.===
