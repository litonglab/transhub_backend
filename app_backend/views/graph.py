import logging
import os

from flask import send_file, Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity

from app_backend.decorators.validators import validate_request, get_validated_data
from app_backend.model.graph_model import graph_model
from app_backend.validators.schemas import GraphSchema
from app_backend.vo import HttpResponse

graph_bp = Blueprint('graph', __name__)
logger = logging.getLogger(__name__)


@graph_bp.route("/graph_get_graph", methods=["POST"])
@jwt_required()
@validate_request(GraphSchema)
def get_graph():
    data = get_validated_data(GraphSchema)
    task_id = data.task_id
    graph_type = data.graph_type
    user_id = get_jwt_identity()

    # 性能图所有用户都可查询，无需验证user_id
    logger.debug(f"Graph request for task {task_id}, type {graph_type} by user {user_id}")
    graph = graph_model.query.filter_by(task_id=task_id, graph_type=graph_type).first()
    if not graph or not os.path.exists(graph.graph_path):
        logger.warning(
            f"Graph not found or file missing: task_id={task_id}, type={graph_type}, path={graph.graph_path if graph else 'None'}")
        return HttpResponse.fail("No such graph or graph file does not exist.")
    logger.info(f"Sending graph file: {graph.graph_path}")
    return send_file(graph.graph_path, mimetype='image/svg+xml', as_attachment=True)
