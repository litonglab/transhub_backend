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
                "allow_rank_delete": False,  # 是否允许用户删除自己的榜单记录，禁止后用户将无法删除自己的榜单记录，管理员不受限制，不配置默认为False
                "force_all_traces_before_seconds": 3 * 24 * 60 * 60,  # 在比赛截止前一段时间（秒），强制评测所有Trace。不配置默认为3天
                "start_time": "2025-01-01 00:00:00",  # 课程开始时间，只有在此时间内才能提交，登录不受限制，管理员不受限制
                "end_time": "2025-01-01 21:00:00",  # 课程结束时间，超过此时间将无法提交，管理员不受限制
                "trace": {  # trace配置
                    # key为trace名称，必须唯一。需配置Trace网络环境，以及上下行文件名称。上下行文件放在课程目录的trace文件夹内。
                    # block表示是否屏蔽该trace的信息，屏蔽后用户不可查看性能图、日志及环境信息，比赛结束后会自动开放查看，管理员不受限制
                    # score_weights表示各项分数占比，计入总分时会根据此权重计算。
                    # 时延配置是单向时延，前端显示的是往返时延（RTT），即2倍的单向时延。
                    # buffer是缓冲区大小，单位为字节，应根据BDP设置。丢包率设置为0-1.0之间的浮点数。
                    "trace_a": {"block": False, "loss_rate": 0.0, "buffer_size": 20, "delay": 20,
                                "downlink_file": "Verizon-LTE-short.down", "uplink_file": "Verizon-LTE-short.up",
                                "score_weights": {"loss": 0.3, "delay": 0.35, "throughput": 0.35}},
                    "Verizon-LTE-example": {"block": False, "loss_rate": 0.0, "buffer_size": 250, "delay": 20,
                                            "downlink_file": "Verizon-LTE-short.down",
                                            "uplink_file": "Verizon-LTE-short.up",
                                            "score_weights": {"loss": 0.3, "delay": 0.35, "throughput": 0.35}}
                },
                # 以下字段由系统生成，无需填写
                # ===system generated start.===
                "path": "",  # 系统生成
                "zhinan_path": "",  # 系统生成
                "image_path": "",  # 系统生成，指南文档的图片路径
                "trace_path": "",  # 系统生成，trace文件的路径
                "student_list": [],  # 系统生成
                # "cca_guide_path": "",  # 系统生成，此字段暂未使用
                # "user_guide_path": "",  # 系统生成，此字段暂未使用
                # ===system generated end.===
            },
            "2025计算机网络校内赛": {
                "name": "competition2025",
                "max_active_uploads_per_user": 3,
                "allow_login": True,
                "allow_rank_delete": False,  # 是否允许用户删除自己的榜单记录，禁止后用户将无法删除自己的榜单记录，管理员不受限制，不配置默认为False
                "force_all_traces_before_seconds": 3 * 24 * 60 * 60,  # 在比赛截止前一段时间（秒），强制评测所有Trace。不配置默认为3天
                "start_time": "2025-01-01 00:00:00",
                "end_time": "2025-01-01 21:00:00",
                "trace": {
                    "trace_a": {"block": False, "loss_rate": 0.0, "buffer_size": 20, "delay": 20,
                                "downlink_file": "Verizon-LTE-short.down", "uplink_file": "Verizon-LTE-short.up",
                                "score_weights": {"loss": 0.3, "delay": 0.35, "throughput": 0.35}},
                    "Verizon-LTE-example": {"block": False, "loss_rate": 0.0, "buffer_size": 250, "delay": 20,
                                            "downlink_file": "Verizon-LTE-short.down",
                                            "uplink_file": "Verizon-LTE-short.up",
                                            "score_weights": {"loss": 0.3, "delay": 0.35, "throughput": 0.35}}
                },
                # 以下字段由系统生成，无需填写
                # ===system generated start.===
                "path": "",  # 系统生成
                "zhinan_path": "",  # 系统生成
                "image_path": "",  # 系统生成，指南文档的图片路径
                "trace_path": "",  # 系统生成，trace文件的路径
                "student_list": [],  # 系统生成
                # "cca_guide_path": "",  # 系统生成，此字段暂未使用
                # "user_guide_path": "",  # 系统生成，此字段暂未使用
                # ===system generated end.===
            }
        }
