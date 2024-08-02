from flask import send_file, jsonify, Blueprint, request

from app_backend.model.graph_model import graph_model
from app_backend.security.safe_check import check_task_auth, check_user_state

graph_bp = Blueprint('graph', __name__)


@graph_bp.route("/get_graph", methods=["POST"])
def get_graph():
    data = request.get_json()
    task_id = data.get("task_id")
    graph_type = data.get("graph_type")
    user_id = data.get("user_id")

    if not check_user_state(user_id):
        return jsonify({"code": 400, "message": "User is not login."})

    if not check_task_auth(task_id, user_id):
        return jsonify({"code": 400, "message": "User is not authorized to access this task."})

    graph = graph_model.query.filter_by(task_id=task_id, graph_type=graph_type).first()
    if graph:
        try:
            response = send_file(graph.graph_path, as_attachment=True)
            return response
        except Exception as e:
            return jsonify({"code": 500,
                            "message": "{} Maybe you algorithm is still running or its result was wrong. You can "
                                       "rerun your code to generate graph.".format(
                                e)})
    else:
        return jsonify({"code": 404, "message": "No such graph."})




# @graph_bp.route("/get_loss_throughput_graph/<task_id>", methods=["GET"])
# def return_loss_throughput_graph(task_id):
#     directory = "/home/liuwei/Transhub_data/cc_training/{}/sourdough/datagrump/result/".format(task_id)
#     try:
#         response = send_file(directory + "throughput_loss_trace.png", cache_timeout=0, as_attachment=True)
#         return response
#     except Exception as e:
#         return jsonify({"code": 500,
#                         "message": "{} Maybe you algorithm is still running or its result was wrong. You can rerun your code to generate graph.".format(
#                             e)})
#
#
# @graph_bp.route("/get_loss_delay_graph/<task_id>", methods=["GET"])
# def return_loss_delay_graph(task_id):
#     directory = "/home/liuwei/Transhub_data/cc_training/{}/sourdough/datagrump/result/".format(task_id)
#     try:
#         response = send_file(directory + "delay_loss_trace.png", cache_timeout=0, as_attachment=True)
#         return response
#     except Exception as e:
#         return jsonify({"code": 500,
#                         "message": "{} Maybe you algorithm is still running or its result was wrong. You can rerun your code to generate graph.".format(
#                             e)})
#
#
# @graph_bp.route("/get_throughput_graph/<task_id>", methods=["GET"])
# def return_throughput_graph(task_id):
#     directory = "/home/liuwei/Transhub_data/cc_training/{}/sourdough/datagrump/result/".format(task_id)
#     try:
#         response = send_file(directory + "throughput.png", cache_timeout=0, as_attachment=True)
#         return response
#     except Exception as e:
#         return jsonify({"code": 500,
#                         "message": "{} Maybe you algorithm is still running or its result was wrong. You can rerun your code to generate graph.".format(
#                             e)})
#
#
# @graph_bp.route("/get_delay_graph/<task_id>", methods=["GET"])
# def return_delay_graph(task_id):
#     directory = "/home/liuwei/Transhub_data/cc_training/{}/sourdough/datagrump/result/".format(task_id)
#     try:
#         response = send_file(directory + "delay.png", cache_timeout=0, as_attachment=True)
#         return response
#     except Exception as e:
#         return jsonify({"code": 500,
#                         "message": "{} Maybe you algorithm is still running or its result was wrong. You can rerun your code to generate graph.".format(
#                             e)})
