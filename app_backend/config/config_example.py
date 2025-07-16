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
            "2025春计算机网络": {  # 课程名称，为【唯一】标识符，请注意不要重复，建议加上时间，如2025春
                "name": "network_class2025",  # 课程文件夹，也保持唯一
                # 每个用户可提交的最大文件数量，管理员不受限制，处于队列中和运行中的任务对应的upload数量超过此数值后将无法再继续上传
                "max_active_uploads_per_user": 3,
                "allow_login": True,  # 是否允许登录，禁止后用户将无法登录此课程，管理员不受限制
                "start_time": "2025-01-01 00:00:00",  # 课程开始时间，只有在此时间内才能提交，登录不受限制，管理员不受限制
                "end_time": "2025-01-01 21:00:00",  # 课程结束时间，超过此时间将无法提交，管理员不受限制
                "trace": {  # trace配置，default必须配置，如果没有为某个trace单独配置，则使用default配置
                    "default": {
                        # 是否屏蔽该trace的信息，屏蔽后用户不可查看性能图、日志及环境信息，比赛结束后会自动开放查看，管理员不受限制
                        "block": False,
                        "network": [  # 网络环境信息配置，可配置多个不同的环境
                            {
                                "loss_rate": 0.0,  # 丢包率
                                "buffer_size": 20,  # 缓冲区大小
                                "delay": 20  # 延迟，单位为毫秒
                            },
                            {
                                "loss_rate": 0.0,  # 丢包率
                                "buffer_size": 250,  # 缓冲区大小
                                "delay": 20  # 延迟，单位为毫秒
                            }
                        ]
                    },
                    "Verizon-LTE-example": {  # trace名称：Verizon-LTE-example
                        # 是否屏蔽该trace的信息，屏蔽后用户不可查看性能图、日志及环境信息，比赛结束后会自动开放查看，管理员不受限制
                        "block": False,
                        "network": [  # 网络环境信息配置，可配置多个不同的环境
                            {
                                "loss_rate": 0.0,  # 丢包率
                                "buffer_size": 20,  # 缓冲区大小
                                "delay": 20  # 延迟，单位为毫秒
                            },
                            {
                                "loss_rate": 0.0,  # 丢包率
                                "buffer_size": 250,  # 缓冲区大小
                                "delay": 20  # 延迟，单位为毫秒
                            }
                        ]
                    }
                },
                # 以下字段由系统生成，无需填写
                # ===system generated start.===
                "path": "",  # 系统生成
                "zhinan_path": "",  # 系统生成
                "image_path": "",  # 系统生成，指南文档的图片路径
                "downlink_dir": "",  # 系统生成
                "uplink_dir": "",  # 系统生成
                "student_list": [],  # 系统生成
                "trace_files": [],  # 系统生成，从 uplink_dir 和 downlink_dir 目录中自动读取的 trace 文件列表
                # "cca_guide_path": "",  # 系统生成，此字段暂未使用
                # "user_guide_path": "",  # 系统生成，此字段暂未使用
                # ===system generated end.===
            },
            "2025计算机网络校内赛": {  # 课程名称，为【唯一】标识符，请注意不要重复，建议加上时间，如2025春
                "name": "competition2025",  # 课程文件夹，也保持唯一
                # 每个用户可提交的最大文件数量，管理员不受限制，处于队列中和运行中的任务对应的upload数量超过此数值后将无法再继续上传
                "max_active_uploads_per_user": 3,
                "allow_login": True,  # 是否允许登录，禁止后用户将无法登录此课程，管理员不受限制
                "start_time": "2025-01-01 00:00:00",  # 课程开始时间，只有在此时间内才能提交，登录不受限制，管理员不受限制
                "end_time": "2025-01-01 21:00:00",  # 课程结束时间，超过此时间将无法提交，管理员不受限制
                "trace": {  # trace配置，default必须配置，如果没有为某个trace单独配置，则使用default配置
                    "default": {
                        # 是否屏蔽该trace的信息，屏蔽后用户不可查看性能图、日志及环境信息，比赛结束后会自动开放查看，管理员不受限制
                        "block": False,
                        "network": [  # 网络环境信息配置，可配置多个不同的环境
                            {
                                "loss_rate": 0.0,  # 丢包率
                                "buffer_size": 20,  # 缓冲区大小
                                "delay": 20  # 延迟，单位为毫秒
                            },
                            {
                                "loss_rate": 0.0,  # 丢包率
                                "buffer_size": 250,  # 缓冲区大小
                                "delay": 20  # 延迟，单位为毫秒
                            }
                        ]
                    },
                    "Verizon-LTE-example": {  # trace名称：Verizon-LTE-example
                        # 是否屏蔽该trace的信息，屏蔽后用户不可查看性能图、日志及环境信息，比赛结束后会自动开放查看，管理员不受限制
                        "block": False,
                        "network": [  # 网络环境信息配置，可配置多个不同的环境
                            {
                                "loss_rate": 0.0,  # 丢包率
                                "buffer_size": 20,  # 缓冲区大小
                                "delay": 20  # 延迟，单位为毫秒
                            },
                            {
                                "loss_rate": 0.0,  # 丢包率
                                "buffer_size": 250,  # 缓冲区大小
                                "delay": 20  # 延迟，单位为毫秒
                            }
                        ]
                    }
                },
                # 以下字段由系统生成，无需填写
                # ===system generated start.===
                "path": "",  # 系统生成
                "zhinan_path": "",  # 系统生成
                "image_path": "",  # 系统生成，指南文档的图片路径
                "downlink_dir": "",  # 系统生成
                "uplink_dir": "",  # 系统生成
                "student_list": [],  # 系统生成
                "trace_files": [],  # 系统生成，从 uplink_dir 和 downlink_dir 目录中自动读取的 trace 文件列表
                # "cca_guide_path": "",  # 系统生成，此字段暂未使用
                # "user_guide_path": "",  # 系统生成，此字段暂未使用
                # ===system generated end.===
            }
        }
