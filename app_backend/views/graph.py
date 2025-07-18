import logging
import os

from flask import Blueprint
from flask_jwt_extended import jwt_required, get_jwt, current_user

from app_backend import get_default_config
from app_backend.model.graph_model import GraphModel
from app_backend.model.task_model import TaskModel
from app_backend.validators.decorators import validate_request, get_validated_data
from app_backend.validators.schemas import GraphSchema
from app_backend.vo.http_response import HttpResponse

graph_bp = Blueprint('graph', __name__)
logger = logging.getLogger(__name__)
config = get_default_config()


@graph_bp.route("/graph_get_graph", methods=["GET"])
@jwt_required()
@validate_request(GraphSchema)
def get_graph():
    data = get_validated_data(GraphSchema)
    task_id = data.task_id
    graph_type = data.graph_type
    user = current_user
    cname = get_jwt().get('cname')

    # 管理员可查询所有课程的图
    if current_user.is_admin():
        logger.debug(f"Admin {current_user.username} requesting graph for task {task_id}, type {graph_type}")
        task = TaskModel.query.filter_by(task_id=task_id).first()
    # 普通用户保证只能查询当前课程（比赛）的图
    else:
        logger.debug(f"User {user.username} requesting graph for task {task_id}, type {graph_type}")
        task = TaskModel.query.filter_by(task_id=task_id, cname=cname).first()

    if not task:
        logger.warning(f"Graph request failed: Task not found for task_id {task_id}")
        return HttpResponse.not_found("任务不存在")
    # 判断性能图是否被屏蔽
    if not config.is_trace_available(cname, task.trace_name):
        logger.warning(f"Graph request blocked for task {task_id}, type {graph_type} by user {user.username}")
        return HttpResponse.fail("此性能图已被屏蔽，比赛结束后可查看")

    # 性能图所有用户都可查询，无需验证user_id
    logger.debug(f"Graph request for task {task_id}, type {graph_type} by user {user.username}")
    graph = GraphModel.query.filter_by(task_id=task_id, graph_type=graph_type).first()
    if not graph or not os.path.exists(graph.graph_path):
        logger.warning(
            f"Graph not found or file missing: task_id={task_id}, type={graph_type}, path={graph.graph_path if graph else 'None'}")
        return HttpResponse.not_found("图片不存在或已被删除")
    logger.info(f"Sending graph file: {graph.graph_path}")
    return HttpResponse.send_attachment_file(graph.graph_path)
