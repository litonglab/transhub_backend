"""
基础配置，读取环境变量，无需修改。
需要在其他模块中使用的配置才写入此处。
"""

import os
import time
from typing import Dict, Any

from app_backend.config import env_file


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

    class Cache:
        """缓存配置"""
        # Redis 配置 - 开发环境使用不同的数据库
        FLASK_REDIS_URL = _get_env_variable('FLASK_REDIS_URL')

    class Security:
        """安全配置"""
        # CORS 配置 - 开发环境允许所有来源
        CORS_ORIGINS = _get_env_variable('CORS_ORIGINS')
        JWT_ACCESS_TOKEN_EXPIRES = int(_get_env_variable('FLASK_JWT_ACCESS_TOKEN_EXPIRES'))

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

    class DramatiqDashboard:
        """DRAMATIQ_DASHBOARD后台配置"""
        DRAMATIQ_DASHBOARD_USERNAME = os.getenv('DRAMATIQ_DASHBOARD_USERNAME')
        DRAMATIQ_DASHBOARD_PASSWORD = os.getenv('DRAMATIQ_DASHBOARD_PASSWORD')
        DRAMATIQ_DASHBOARD_URL = os.getenv('DRAMATIQ_DASHBOARD_URL')
        # 必须设置上述三个环境变量，且不能为空，否则不启用DRAMATIQ_DASHBOARD
        DRAMATIQ_DASHBOARD_ENABLED = DRAMATIQ_DASHBOARD_USERNAME and DRAMATIQ_DASHBOARD_PASSWORD and DRAMATIQ_DASHBOARD_URL and len(
            DRAMATIQ_DASHBOARD_USERNAME) > 0 and len(DRAMATIQ_DASHBOARD_PASSWORD) > 0 and len(
            DRAMATIQ_DASHBOARD_URL) > 0

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
            config["downlink_dir"] = os.path.join(config["path"], 'test_data', 'downlink')
            config["uplink_dir"] = os.path.join(config["path"], 'test_data', 'uplink')
            config["student_list"] = []

            # 读取学生列表
            student_list_path = os.path.join(config["path"], 'student_list.txt')
            if os.path.exists(student_list_path):
                with open(student_list_path, 'r') as f:
                    config["student_list"] = [line.strip() for line in f if line.strip()]
                    self.Course.REGISTER_STUDENT_LIST.update(config["student_list"])
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

    def is_trace_blocked(self, cname: str, trace_name: str) -> bool:
        """检查指定课程某个trace是否被屏蔽"""
        # 如果当前时间不在比赛时间内，则不屏蔽trace
        if not self.is_now_in_competition(cname):
            return False

        trace_conf = self.get_course_trace_config(cname, trace_name)
        return trace_conf['block']
