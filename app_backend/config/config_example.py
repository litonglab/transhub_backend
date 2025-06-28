"""
环境配置示例
复制此文件为 development.py （开发环境）或 production.py （生产环境），并根据需要修改配置。
"""

from app_backend.config.base import BaseConfig


# 真实配置文件不上传git
# ！开发环境需将 ExampleConfig 设置为 DevelopmentConfig，生产环境需设置为 ProductionConfig
class ExampleConfig(BaseConfig):
    """示例环境配置"""

    class Course:
        """课程配置"""
        ALL_CLASS = {
            "计算机系统基础II": {
                "name": "pantheon-ics",
                "allow_login": True,  # 是否允许登录
                "start_time": "2025-01-01 00:00:00",  # 课程开始时间，只有在此时间内才能提交，登录不受限制
                "end_time": "2025-01-01 21:00:00",  # 课程结束时间，超过此时间将无法提交
                "trace": {  # trace配置，default必须配置，如果没有为trace单独配置，则使用default配置
                    "default": {
                        # 环境信息配置会排列组合
                        "loss_rate": [0.0],  # 丢包率
                        "buffer_size": [20, 250],  # 缓冲区大小
                        "block": False  # 是否屏蔽该trace的信息，屏蔽后用户不可查看性能图、日志及环境信息，比赛结束后会自动开放查看
                    },
                    "Verizon-LTE-example": {  # trace名称：Verizon-LTE-example
                        # 环境信息配置会排列组合
                        "loss_rate": [0.1],  # 丢包率
                        "buffer_size": [50, 300],  # 缓冲区大小
                        "block": True  # 是否屏蔽该trace的信息，屏蔽后用户不可查看性能图、日志及环境信息，比赛结束后会自动开放查看
                    }
                },
                # 以下字段由系统生成，无需填写
                # ===system generated start.===
                "path": "",  # 系统生成
                "zhinan_path": "",  # 系统生成
                "downlink_dir": "",  # 系统生成
                "uplink_dir": "",  # 系统生成
                "student_list": [],  # 系统生成
                "trace_files": [],  # 系统生成，从 uplink_dir 和 downlink_dir 目录中自动读取的 trace 文件列表
                # "cca_guide_path": "",  # 系统生成，此字段暂未使用
                # "user_guide_path": "",  # 系统生成，此字段暂未使用
                # ===system generated end.===
            },
            "计算机网络": {
                "name": "pantheon-network",
                "allow_login": True,  # 是否允许登录
                "start_time": "2024-01-01 00:00:00",  # 课程开始时间，只有在此时间内才能提交，登录不受限制
                "end_time": "2025-01-01 21:00:00",  # 课程结束时间，超过此时间将无法提交
                "trace": {  # trace配置，default必须配置，如果没有为trace单独配置，则使用default配置
                    "default": {
                        # 环境信息配置会排列组合
                        "loss_rate": [0.0],  # 丢包率
                        "buffer_size": [20, 250],  # 缓冲区大小
                        "block": False  # 是否屏蔽该trace的信息，屏蔽后用户不可查看性能图、日志及环境信息，比赛结束后会自动开放查看
                    },
                    "Verizon-LTE-example": {  # trace名称：Verizon-LTE-example
                        # 环境信息配置会排列组合
                        "loss_rate": [0.1],  # 丢包率
                        "buffer_size": [50, 300],  # 缓冲区大小
                        "block": True  # 是否屏蔽该trace的信息，屏蔽后用户不可查看性能图、日志及环境信息，比赛结束后会自动开放查看
                    }
                },
                # 以下字段由系统生成，无需填写
                # ===system generated start.===
                "path": "",  # 系统生成
                "zhinan_path": "",  # 系统生成
                "downlink_dir": "",  # 系统生成
                "uplink_dir": "",  # 系统生成
                "student_list": [],  # 系统生成
                "trace_files": [],  # 系统生成，从 uplink_dir 和 downlink_dir 目录中自动读取的 trace 文件列表
                # "cca_guide_path": "",  # 系统生成，此字段暂未使用
                # "user_guide_path": "",  # 系统生成，此字段暂未使用
                # ===system generated end.===
            }
        }
