"""
基础配置，读取环境变量，无需修改。
需要在其他模块中使用的配置才写入此处。
"""

import os
import time
from typing import Dict, Any

from app_backend.config import env_file
from app_backend.security.bypass_decorators import admin_bypass


# 由于循环导入，此模块不允许使用logger


def _get_env_variable(name: str) -> Any:
    value = os.getenv(name)
    if value is None:
        raise ValueError(f"环境变量 {name} 未配置，请在 {env_file} 文件中配置")
    return value


class BaseConfig:
    """开发环境配置"""

    class App:
        """应用基础配置"""
        NAME = _get_env_variable('APP_NAME')
        BASEDIR = _get_env_variable('BASEDIR')
        USER_DIR_PATH = os.path.join(BASEDIR, "user_data")
        SENDER_MAX_WINDOW_SIZE = int(_get_env_variable('SENDER_MAX_WINDOW_SIZE'))

    class Cache:
        """缓存配置"""
        # Redis 配置 - 开发环境使用不同的数据库
        FLASK_REDIS_URL = _get_env_variable('FLASK_REDIS_URL')

    class Security:
        """安全配置"""
        # CORS 配置 - 开发环境允许所有来源
        CORS_ORIGINS = _get_env_variable('CORS_ORIGINS')
        JWT_ACCESS_TOKEN_EXPIRES = int(_get_env_variable('FLASK_JWT_ACCESS_TOKEN_EXPIRES'))

    class SuperAdmin:
        """超级管理员配置"""
        USERNAME = os.getenv('SUPER_ADMIN_USERNAME')
        PASSWORD = os.getenv('SUPER_ADMIN_PASSWORD')
        REAL_NAME = os.getenv('SUPER_ADMIN_REAL_NAME', '系统管理员')

        # 检查是否配置了必要的超级管理员信息
        ENABLED = USERNAME and PASSWORD and len(USERNAME) > 0 and len(PASSWORD) > 0

    class Logging:
        """日志配置"""
        # 开发环境使用更详细的日志
        LOG_DIR = _get_env_variable('LOG_DIR')
        LOG_LEVEL = _get_env_variable('LOG_LEVEL')
        LOG_MAX_BYTES = int(_get_env_variable('LOG_MAX_BYTES'))
        LOG_BACKUP_COUNT = int(_get_env_variable('LOG_BACKUP_COUNT'))
        LOG_FILENAME = _get_env_variable('LOG_FILENAME')

    class Course:
        """课程配置，在对应的环境文件中定义"""
        ALL_CLASS = {}
        CNAME_LIST = list()
        REGISTER_STUDENT_LIST = list()

    def __init__(self):
        """初始化配置"""
        self._setup_class_config()

    def _setup_class_config(self):
        """设置课程配置"""
        self.Course.CNAME_LIST = list(self.Course.ALL_CLASS.keys())
        self.Course.REGISTER_STUDENT_LIST = set()

        # 填充课程路径配置
        for cname, config in self.Course.ALL_CLASS.items():
            config["path"] = os.path.join(self.App.BASEDIR, config["name"])
            config["zhinan_path"] = os.path.join(config["path"], 'help', 'zhinan.md')
            config["image_path"] = os.path.join(config["path"], 'help', 'images')
            config["downlink_dir"] = os.path.join(config["path"], 'test_data', 'downlink')
            config["uplink_dir"] = os.path.join(config["path"], 'test_data', 'uplink')
            config["student_list"] = []
            config["trace_files"] = []

            # 读取学生列表
            student_list_path = os.path.join(config["path"], 'student_list.txt')
            if os.path.exists(student_list_path):
                with open(student_list_path, 'r') as f:
                    config["student_list"] = [line.strip() for line in f if line.strip()]
                    self.Course.REGISTER_STUDENT_LIST.update(config["student_list"])

            # 读取 trace 文件列表
            uplink_dir = config["uplink_dir"]
            downlink_dir = config["downlink_dir"]
            if os.path.exists(uplink_dir):
                for trace_file in os.listdir(uplink_dir):
                    # 假设 trace 文件以 .up 结尾
                    if trace_file.endswith('.up'):
                        trace_name = trace_file[:-3]  # 去掉 .up 扩展名
                        # 检查下行目录中是否存在对应的 .down 文件
                        downlink_file = trace_name + '.down'
                        downlink_file_path = os.path.join(downlink_dir, downlink_file)
                        if os.path.exists(downlink_file_path):
                            config["trace_files"].append(trace_name)
        self.Course.REGISTER_STUDENT_LIST = list(self.Course.REGISTER_STUDENT_LIST)

    def to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典，包括嵌套类的属性"""

        def _convert_to_dict(obj) -> Dict[str, Any]:
            result = {}
            for key in dir(obj):
                if not key.startswith('_') and key != 'to_dict':
                    value = getattr(obj, key)
                    # 检查是否是类属性
                    if isinstance(value, type) and hasattr(value, '__dict__'):
                        # 获取类的所有属性
                        class_dict = {}
                        for attr_name in dir(value):
                            if not attr_name.startswith('_') and not callable(getattr(value, attr_name)):
                                class_dict[attr_name] = getattr(value, attr_name)
                        result[key] = class_dict
                    else:
                        result[key] = value
            return result

        config_dict = _convert_to_dict(self)

        config_dict['Cache']['FLASK_REDIS_URL'] = '******'
        return config_dict

    @admin_bypass
    def is_now_in_competition(self, cname: str) -> bool:
        """检查当前时间是否在指定课程的比赛时间内"""
        _config = self.Course.ALL_CLASS[cname]
        start_time = time.mktime(time.strptime(_config['start_time'], "%Y-%m-%d %H:%M:%S"))
        end_time = time.mktime(time.strptime(_config['end_time'], "%Y-%m-%d %H:%M:%S"))
        now_time = time.time()
        return start_time <= now_time <= end_time

    def get_course_config(self, cname: str) -> Dict[str, Any]:
        """获取指定课程的配置"""
        if cname not in self.Course.ALL_CLASS:
            raise ValueError(f"课程 {cname} 不存在，请检查配置")
        return self.Course.ALL_CLASS[cname]

    def get_course_trace_config(self, cname: str, trace_name: str) -> Dict[str, Any]:
        """获取指定课程某个trace的配置"""
        course = self.get_course_config(cname)
        trace_dict = course["trace"]
        if trace_name not in trace_dict:
            assert "default" in trace_dict, f"课程 {cname} 的trace配置中未配置default项，请检查配置"
            return trace_dict["default"]
        return trace_dict[trace_name]

    def get_course_trace_files(self, cname: str) -> list:
        """获取指定课程的 trace 文件列表"""
        course_config = self.get_course_config(cname)
        return course_config["trace_files"]

    @admin_bypass
    def is_trace_available(self, cname: str, trace_name: str) -> bool:
        """检查指定课程某个trace是否可用，如果用户是管理员，则不屏蔽trace。

        Args:
            cname: 课程名称
            trace_name: trace名称
        """
        # 如果当前时间不在比赛时间内，则不屏蔽trace
        if not self.is_now_in_competition(cname):
            return True

        trace_conf = self.get_course_trace_config(cname, trace_name)
        return not trace_conf['block']
