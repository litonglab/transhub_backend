import os

from flask import send_file, Blueprint, request, abort
from flask_jwt_extended import jwt_required, get_jwt_identity

from app_backend.decorators.validators import validate_request
from app_backend.model.graph_model import graph_model
from app_backend.validators.schemas import GraphSchema

graph_bp = Blueprint('graph', __name__)


@graph_bp.route("/graph_get_graph", methods=["POST"])
@jwt_required()
@validate_request(GraphSchema)
def get_graph():
    data = request.validated_data
    task_id = data.task_id
    graph_type = data.graph_type
    user_id = get_jwt_identity()

    # if not check_user_state(user_id):
    #     return abort(400, "Please login firstly.")
    #
    # if not check_task_auth(user_id, task_id):
    #     return abort(400, "User is not authorized to access this task.")
    # 性能图所有用户都可查询，无需验证user_id
    graph = graph_model.query.filter_by(task_id=task_id, graph_type=graph_type).first()
    if not graph:
        return abort(400, "No such graph.")
    if not os.path.exists(graph.graph_path):
        print("path无效")
    if graph:
        try:
            print(graph.graph_path)
            return send_file(graph.graph_path, mimetype='image/svg+xml', as_attachment=True)
        except Exception as e:
            return abort(500,
                         f"Maybe your algorithm is still running or its result was wrong. You can rerun your code to generate the graph. Error: {e}")
    else:
        return abort(400, "No such graph.")
