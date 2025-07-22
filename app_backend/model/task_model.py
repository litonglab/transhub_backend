import logging
import re
import uuid
from datetime import datetime
from enum import Enum

from flask_jwt_extended import current_user
from sqlalchemy import func, text
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.dialects.mysql import VARCHAR
from sqlalchemy.orm import deferred

from app_backend import db, get_default_config
from app_backend.security.bypass_decorators import admin_bypass

logger = logging.getLogger(__name__)
config = get_default_config()


class TaskStatus(Enum):
    """任务状态枚举类，注意需要新添加状态时，需要更新状态优先级及状态转换等内容"""
    QUEUED = 'queued'  # 任务已入队
    COMPILING = 'compiling'  # 正在编译
    COMPILED = 'compiled'  # 编译完成
    COMPILED_FAILED = 'compile_failed'  # 编译失败
    RUNNING = 'running'  # 正在运行
    FINISHED = 'finished'  # 已完成
    ERROR = 'error'  # 发生错误
    NOT_QUEUED = 'not_queued'  # 未能入队

    @property
    def priority(self):
        """获取状态优先级，数字越小优先级越高，用于to_history_dict()
           状态优先级：compiled_failed > error > not_queued > compiled > compiling > running > queued > finished
        """
        priority_map = {
            TaskStatus.COMPILED_FAILED: 0,
            TaskStatus.ERROR: 1,
            TaskStatus.COMPILED: 2,
            TaskStatus.COMPILING: 3,
            TaskStatus.RUNNING: 4,
            TaskStatus.QUEUED: 5,
            TaskStatus.NOT_QUEUED: 6,
            TaskStatus.FINISHED: 7
        }
        return priority_map[self]

    @classmethod
    def get_valid_transitions(cls):
        """获取有效的状态转换"""
        return {
            cls.QUEUED: [cls.COMPILING, cls.ERROR, cls.COMPILED],
            cls.COMPILING: [cls.COMPILED, cls.ERROR, cls.COMPILED_FAILED],
            cls.COMPILED: [cls.RUNNING, cls.ERROR],
            cls.RUNNING: [cls.FINISHED, cls.ERROR],
            # cls.RETRYING: [cls.RUNNING, cls.ERROR],
            cls.FINISHED: [cls.ERROR],
            cls.ERROR: [],
            cls.NOT_QUEUED: [cls.QUEUED],
            cls.COMPILED_FAILED: [cls.ERROR],
        }

    def can_transition_to(self, new_status):
        """检查是否可以转换到新状态"""
        if not isinstance(new_status, TaskStatus):
            new_status = TaskStatus(new_status)
        return new_status in self.get_valid_transitions()[self]


# Define the maximum length, also used in the validator schema
TASK_MODEL_ALGORITHM_MAX_LEN = 50
TASK_MODEL_ERROR_LOG_MAX_LEN = 16777215  # 16MB, MySQL MEDIUMTEXT max length


def _sanitize_sensitive(_text):
    # 路径脱敏（保留文件名）
    _text = re.sub(r'(/[^/\s]+)+/([^/\s]+)', r'[path_hidden]/\2', _text)
    # 需要脱敏参数的命令列表
    # 日志示例：Died on std::runtime_error: `mm-link Verizon-LTE-140.down Verizon-LTE-140.up --uplink-queue=droptail --uplink-queue-args="packets=250" --once
    # --uplink-log=Verizon-LTE-140.log -- bash -c sender $MAHIMAHI_BASE 50001 > null': process exited with failure status 1
    sensitive_cmds = ['mm-link', 'mm-loss']
    for cmd in sensitive_cmds:
        # 匹配命令本身及其后所有参数，直到下一个单引号或字符串结尾
        _text = re.sub(rf'({cmd})[^\']*', r'\1 [command_hidden]', _text)
    return _text


class TaskModel(db.Model):
    __tablename__ = 'task'
    task_id = db.Column(VARCHAR(36, charset='utf8mb4'), primary_key=True, default=lambda: str(uuid.uuid4()))
    upload_id = db.Column(VARCHAR(36, charset='utf8mb4'), nullable=False)  # 标识是哪次提交, 后续upload应单独建表
    loss_rate = db.Column(db.Float, nullable=False)  # 标识运行的环境,loss_rate
    buffer_size = db.Column(db.Integer, nullable=False)  # 标识运行的环境,buffer_size
    delay = db.Column(db.Integer, nullable=False)  # 标识运行的环境,delay
    trace_name = db.Column(VARCHAR(50, charset='utf8mb4'), nullable=False)  # 标识运行的trace
    user_id = db.Column(VARCHAR(36, charset='utf8mb4'), db.ForeignKey('student.user_id'), nullable=False)
    task_status = db.Column(db.Enum(TaskStatus), nullable=False)
    created_time = db.Column(db.DateTime, nullable=False)  # actually, it's upload time.
    task_score = db.Column(db.Float, server_default=text("0"), nullable=False)  # 任务分数，默认0
    loss_score = db.Column(db.Float, server_default=text("0"), nullable=False)  # 丢包原始分数，默认0
    delay_score = db.Column(db.Float, server_default=text("0"), nullable=False)  # 时延原始分数，默认0
    throughput_score = db.Column(db.Float, server_default=text("0"), nullable=False)  # 吞吐原始分数，默认0
    cname = db.Column(VARCHAR(50, charset='utf8mb4'), nullable=False)  # 后续修改相关查询逻辑后可删除
    competition_id = db.Column(db.Integer, db.ForeignKey('competition.id'), nullable=False)
    task_dir = db.Column(VARCHAR(256, charset='utf8mb4'), nullable=False)  # 任务的文件夹, 用于存放用户上传的文件
    algorithm = db.Column(VARCHAR(TASK_MODEL_ALGORITHM_MAX_LEN, charset='utf8mb4'), nullable=False)  # 算法名称
    # ⚠️⚠️⚠️❗️❗️❗️注意此处可能导致性能问题
    # error_log 最大16MB，使用deferred延迟加载
    # 请注意涉及task查询时的性能问题，例如以下代码使用count()会导致error_log被加载
    # count = TaskModel.query.filter(
    #     TaskModel.cname == cname,
    #     TaskModel.task_status == status
    # ).count() 如需计数，请使用TaskModel.count()方法
    # 以下代码不会导致error_log被加载，除非显式调用error_log属性
    # TaskModel.query.filter_by(user_id=user.user_id, cname=cname)
    # 如果不确定，请将日志级别设置为debug（debug下默认打印query语句）或
    # 通过日志手动打印query语句检查是否不必要地加载了error_log
    error_log = deferred(db.Column(MEDIUMTEXT(charset='utf8mb4'), nullable=False))  # 错误日志，默认不加载
    created_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=func.now(),
                           onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f'<Task {self.task_id}>'

    def save(self):
        logger.debug(f"[task: {self.task_id}] Saving task for user {self.user_id}")
        try:
            db.session.add(self)
            db.session.commit()
            logger.info(f"[task: {self.task_id}] Task saved successfully")
        except Exception as e:
            logger.error(f"[task: {self.task_id}] Error saving task: {str(e)}", exc_info=True)
            db.session.rollback()
            raise

    @classmethod
    def count(cls, **kwargs):
        """
        高效地统计符合条件的任务数量，避免加载整个对象。
        :param kwargs: 过滤条件，例如 cname='some_course', task_status=TaskStatus.RUNNING
        :return: 任务数量 (int)
        """
        query = db.session.query(func.count(cls.task_id))
        if kwargs:
            query = query.filter_by(**kwargs)
        return query.scalar()

    def update_task_log(self, log_content):
        """
            更新任务日志，更新task对象的日志，到下一次调用TaskModel update时才写入数据库
            :param log_content: 日志内容
            """
        log_content = _sanitize_sensitive(log_content)
        self.error_log += f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {log_content}\n"
        # 按 utf-8 编码后的字节长度判断
        max_bytes = TASK_MODEL_ERROR_LOG_MAX_LEN
        error_log_bytes = self.error_log.encode('utf-8')
        if len(error_log_bytes) > max_bytes:
            logger.warning(
                f"[task: {self.task_id}] task log length {len(error_log_bytes)} bytes exceeds maximum length of {max_bytes} bytes, truncating.")
            truncated = error_log_bytes[:max_bytes - 1000].decode('utf-8', errors='ignore')
            self.error_log = truncated + '...\nlog is too long and has been truncated.'
        logger.info(f"[task: {self.task_id}] Task log updated successfully")

    def update(self, **kwargs):
        logger.debug(f"[task: {self.task_id}] Updating task with parameters: {kwargs}")
        try:
            with db.session.begin_nested():
                # 检查状态转换是否有效
                if 'task_status' in kwargs:
                    current_status = self.task_status
                    new_status = kwargs['task_status']
                    if not current_status.can_transition_to(new_status):
                        raise ValueError(f"Invalid status transition from {current_status.value} to {new_status.value}")
                    logger.info(
                        f"[task: {self.task_id}] Status changing from {current_status.value} to {new_status.value}")
                    self.update_task_log(f"Task status changing: {current_status.value} -> {new_status.value}")

                for key, value in kwargs.items():
                    setattr(self, key, value)
                db.session.commit()
            logger.info(f"[task: {self.task_id}] Task updated successfully")
        except Exception as e:
            logger.error(f"[task: {self.task_id}] Error updating task: {str(e)}", exc_info=True)
            db.session.rollback()
            raise e

    def delete(self):
        logger.info(f"[task: {self.task_id}] Deleting task")
        try:
            db.session.delete(self)
            db.session.commit()
            logger.info(f"[task: {self.task_id}] Task deleted successfully")
        except Exception as e:
            logger.error(f"[task: {self.task_id}] Error deleting task: {str(e)}", exc_info=True)
            db.session.rollback()
            raise

    @admin_bypass
    def log_permission(self):
        """检查日志权限，只能查询自己的任务日志
           即使Trace被屏蔽，仍然可以查询自己的任务日志，用户可以根据收集的日志信息来优化算法
        """
        return current_user.user_id == self.user_id

    def to_detail_dict(self):
        trace_available = config.is_trace_available(self.cname, self.trace_name)
        trace_conf = config.get_course_trace_config(self.cname, self.trace_name)
        block_conf = trace_conf.get('block', False) if trace_conf else False
        res = {
            # 'user_id': self.user_id,
            'task_id': self.task_id,
            'upload_id': self.upload_id,
            'loss_rate': self.loss_rate if trace_available else "*",
            'buffer_size': self.buffer_size if trace_available else "*",
            'delay': self.delay if trace_available else "*",
            'trace_name': f"{self.trace_name} *" if block_conf else self.trace_name,
            'task_status': self.task_status.value,
            'created_time': self.created_time,
            'task_score': self.task_score,
            'loss_score': self.loss_score,
            'delay_score': self.delay_score,
            'throughput_score': self.throughput_score,
            'cname': self.cname,
            'algorithm': self.algorithm,
            'updated_at': self.updated_at,
            'created_at': self.created_at,
            'log': self.log_permission(),  # 返回用户是否具有权限，用于前端显示日志按钮
        }
        return res


def to_history_dict(tasks: list):
    # 将tasks按upload_id聚合，score求和。状态优先级：error > not_queued > compiling > queued > running > finished
    upload_id_dict = {}

    for task in tasks:
        if task.upload_id not in upload_id_dict:
            upload_id_dict[task.upload_id] = {
                "cname": task.cname,
                "algorithm": task.algorithm,
                "created_time": task.created_time,
                "status": task.task_status.value,
                "score": task.task_score,
                "upload_id": task.upload_id,
                'updated_at': task.updated_at,
                'created_at': task.created_at,
            }
        else:
            task_status = task.task_status
            current_status = TaskStatus(upload_id_dict[task.upload_id]['status'])

            # 如果新状态优先级更高，则更新状态
            if task_status.priority < current_status.priority:
                upload_id_dict[task.upload_id]['status'] = task_status.value
                # 如果是error或compiled_failed状态，score设为0
                if task_status in [TaskStatus.ERROR, TaskStatus.COMPILED_FAILED]:
                    upload_id_dict[task.upload_id]['score'] = 0
                    upload_id_dict[task.upload_id]['updated_at'] = task.updated_at
                # 如果是finished状态，累加score
                elif task_status == TaskStatus.FINISHED:
                    upload_id_dict[task.upload_id]['score'] += task.task_score
                    upload_id_dict[task.upload_id]['updated_at'] = task.updated_at
            # 如果是finished状态，累加score
            elif task_status == TaskStatus.FINISHED:
                upload_id_dict[task.upload_id]['score'] += task.task_score
                upload_id_dict[task.upload_id]['updated_at'] = task.updated_at

    return list(upload_id_dict.values())
