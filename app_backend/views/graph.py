import os

from flask import send_file, Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app_backend.decorators.validators import validate_request
from app_backend.model.graph_model import graph_model
from app_backend.validators.schemas import GraphSchema
from app_backend.vo import HttpResponse

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
    if not graph or not os.path.exists(graph.graph_path):
        return HttpResponse.fail("No such graph or graph file does not exist.")
    print(graph.graph_path)
    return send_file(graph.graph_path, mimetype='image/svg+xml', as_attachment=True)
