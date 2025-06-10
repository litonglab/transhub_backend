import logging
from enum import Enum

from sqlalchemy.dialects.mysql import VARCHAR

from app_backend import db

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态枚举类，注意需要新添加状态时，需要更新状态优先级及状态转换等内容"""
    QUEUED = 'queued'  # 任务已入队
    COMPILING = 'compling'  # 正在编译
    COMPILED = 'compiled'  # 编译完成
    COMPILED_FAILED = 'compile_failed'  # 编译失败
    RUNNING = 'running'  # 正在运行
    # RETRYING = 'retrying'       # 重试中
    FINISHED = 'finished'  # 已完成
    ERROR = 'error'  # 发生错误
    NOT_QUEUED = 'not_queued'  # 未能入队

    @property
    def priority(self):
        """获取状态优先级，数字越小优先级越高，用于to_history_dict()
           状态优先级：compiled_failed > error > not_queued > compiled > compling > queued > running > finished
        """
        priority_map = {
            TaskStatus.COMPILED_FAILED: 0,
            TaskStatus.ERROR: 1,
            TaskStatus.NOT_QUEUED: 2,
            TaskStatus.COMPILED: 3,
            TaskStatus.COMPILING: 4,
            TaskStatus.QUEUED: 5,
            TaskStatus.RUNNING: 6,
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
            cls.FINISHED: [],
            cls.ERROR: [],
            cls.NOT_QUEUED: [],
            cls.COMPILED_FAILED: [cls.ERROR],
        }

    def can_transition_to(self, new_status):
        """检查是否可以转换到新状态"""
        if not isinstance(new_status, TaskStatus):
            new_status = TaskStatus(new_status)
        return new_status in self.get_valid_transitions()[self]


class Task_model(db.Model):
    __tablename__ = 'task'
    task_id = db.Column(db.String(36), primary_key=True)
    upload_id = db.Column(db.String(36), nullable=False)  # 标识是哪次提交
    loss_rate = db.Column(db.Float, nullable=False)  # 标识运行的环境,loss_rate
    buffer_size = db.Column(db.Integer, nullable=False)  # 标识运行的环境,buffer_size
    trace_name = db.Column(db.String(50), nullable=False)  # 标识运行的trace
    user_id = db.Column(db.String(36), nullable=False)
    task_status = db.Column(db.String(16), nullable=False)
    created_time = db.Column(db.DateTime, nullable=False)
    # running_port = db.Column(db.Integer)
    task_score = db.Column(db.Float)
    cname = db.Column(VARCHAR(50, charset='utf8mb4'), nullable=False)
    # cname = db.Column(db.String(50))  # 任务类型，可以表示是哪个比赛的任务
    task_dir = db.Column(db.String(256))  # 任务的文件夹, 用于存放用户上传的文件
    algorithm = db.Column(db.String(50))  # 算法名称
    error_log = db.Column(VARCHAR(15000, charset='utf8mb4'), )  # 错误日志

    def __repr__(self):
        return f'<Task {self.task_id}>'

    def save(self):
        logger.debug(f"[task: {self.task_id}] Saving task for user {self.user_id}")
        db.session.add(self)
        db.session.commit()
        logger.info(f"[task: {self.task_id}] Task saved successfully")

    def update(self, **kwargs):
        logger.debug(f"[task: {self.task_id}] Updating task with parameters: {kwargs}")
        try:
            with db.session.begin_nested():
                # 检查状态转换是否有效
                if 'task_status' in kwargs:
                    current_status = TaskStatus(self.task_status)
                    new_status = TaskStatus(kwargs['task_status'])
                    if not current_status.can_transition_to(new_status):
                        raise ValueError(f"Invalid status transition from {current_status.value} to {new_status.value}")
                    logger.info(
                        f"[task: {self.task_id}] Status changing from {current_status.value} to {new_status.value}")

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
        db.session.delete(self)
        db.session.commit()
        logger.info(f"[task: {self.task_id}] Task deleted successfully")

    def to_detail_dict(self):
        status = TaskStatus(self.task_status)
        res = {
            'user_id': self.user_id,
            'task_id': self.task_id,
            'upload_id': self.upload_id,
            'loss_rate': self.loss_rate,
            'buffer_size': self.buffer_size,
            'trace_name': self.trace_name,
            'task_status': self.task_status,
            'created_time': self.created_time.strftime("%Y-%m-%d %H:%M:%S"),
            'task_score': self.task_score,
            'cname': self.cname,
            'algorithm': self.algorithm,
            'log': "No log available for this status, only error tasks have logs.\n当前状态不可查询，只有错误状态的任务才可查询日志。",
        }

        if status == TaskStatus.ERROR or status == TaskStatus.COMPILED_FAILED:
            res['log'] = self.error_log
        return res


def to_history_dict(tasks: list):
    # 将tasks按upload_id聚合，score求和。状态优先级：error > not_queued > compling > queued > running > finished
    upload_id_dict = {}

    for task in tasks:
        if task.upload_id not in upload_id_dict:
            upload_id_dict[task.upload_id] = {
                "cname": task.cname,
                "algorithm": task.algorithm,
                "created_time": task.created_time,
                "status": task.task_status,
                "score": task.task_score,
                "upload_id": task.upload_id
            }
        else:
            task_status = TaskStatus(task.task_status)
            current_status = TaskStatus(upload_id_dict[task.upload_id]['status'])

            # 如果新状态优先级更高，则更新状态
            if task_status.priority < current_status.priority:
                upload_id_dict[task.upload_id]['status'] = task_status.value
                # 如果是error或not_queued或compiled_failed状态，score设为0
                if task_status == TaskStatus.ERROR or task_status == TaskStatus.NOT_QUEUED or task_status == TaskStatus.COMPILED_FAILED:
                    upload_id_dict[task.upload_id]['score'] = 0
                # 如果是finished状态，累加score
                elif task_status == TaskStatus.FINISHED:
                    upload_id_dict[task.upload_id]['score'] += task.task_score
            # 如果当前状态优先级更高，保持当前状态
            elif task_status.priority > current_status.priority:
                continue
            # 如果优先级相同，且是finished状态，累加score
            elif task_status == TaskStatus.FINISHED:
                upload_id_dict[task.upload_id]['score'] += task.task_score

    return list(upload_id_dict.values())
