import logging
import uuid
from datetime import datetime
from enum import Enum

from flask_jwt_extended import current_user
from sqlalchemy import func, text
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.dialects.mysql import VARCHAR

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
            TaskStatus.NOT_QUEUED: 2,
            TaskStatus.COMPILED: 3,
            TaskStatus.COMPILING: 4,
            TaskStatus.RUNNING: 5,
            TaskStatus.QUEUED: 6,
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
            cls.NOT_QUEUED: [],
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
    error_log = db.Column(MEDIUMTEXT(charset='utf8mb4'), nullable=False)  # 错误日志，显示编译或运行日志
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

    def update_task_log(self, log_content):
        """
            更新任务日志，更新task对象的日志，到下一次调用TaskModel update时才写入数据库
            :param log_content: 日志内容
            """
        self.error_log += f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {log_content}\n"
        # 按 utf-8 编码后的字节长度判断
        max_bytes = TASK_MODEL_ERROR_LOG_MAX_LEN
        error_log_bytes = self.error_log.encode('utf-8')
        if len(error_log_bytes) > max_bytes:
            logger.warning(
                f"[task: {self.task_id}] task log length {len(error_log_bytes)} bytes exceeds maximum length of {max_bytes} bytes, truncating.")
            truncated = error_log_bytes[:max_bytes - 100].decode('utf-8', errors='ignore')
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
        res = {
            # 'user_id': self.user_id,
            'task_id': self.task_id,
            'upload_id': self.upload_id,
            'loss_rate': self.loss_rate if trace_available else "*",
            'buffer_size': self.buffer_size if trace_available else "*",
            'delay': self.delay if trace_available else "*",
            'trace_name': self.trace_name,
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
            'log': self.error_log if self.log_permission() else None,
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
                # 如果是error或not_queued或compiled_failed状态，score设为0
                if task_status in [TaskStatus.ERROR, TaskStatus.NOT_QUEUED, TaskStatus.COMPILED_FAILED]:
                    upload_id_dict[task.upload_id]['score'] = 0
                    upload_id_dict[task.upload_id]['updated_at'] = task.updated_at
                # 如果是finished状态，累加score
                elif task_status == TaskStatus.FINISHED:
                    upload_id_dict[task.upload_id]['score'] += task.task_score
                    upload_id_dict[task.upload_id]['updated_at'] = task.updated_at
            # 如果当前状态优先级更高，保持当前状态
            elif task_status.priority > current_status.priority:
                continue
            # 如果优先级相同，且是finished状态，累加score
            elif task_status == TaskStatus.FINISHED:
                upload_id_dict[task.upload_id]['score'] += task.task_score
                upload_id_dict[task.upload_id]['updated_at'] = task.updated_at

    return list(upload_id_dict.values())
