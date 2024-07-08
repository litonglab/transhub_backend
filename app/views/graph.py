from flask import send_file, jsonify, Blueprint

graph_bp = Blueprint('graph', __name__)


@graph_bp.route("/get_loss_throughput_graph/<task_id>", methods=["GET"])
def return_loss_throughput_graph(task_id):
    directory = "/home/liuwei/Transhub_data/cc_training/{}/sourdough/datagrump/result/".format(task_id)
    try:
        response = send_file(directory + "throughput_loss_trace.png", cache_timeout=0, as_attachment=True)
        return response
    except Exception as e:
        return jsonify({"code": 500,
                        "message": "{} Maybe you algorithm is still running or its result was wrong. You can rerun your code to generate graph.".format(
                            e)})


@graph_bp.route("/get_loss_delay_graph/<task_id>", methods=["GET"])
def return_loss_delay_graph(task_id):
    directory = "/home/liuwei/Transhub_data/cc_training/{}/sourdough/datagrump/result/".format(task_id)
    try:
        response = send_file(directory + "delay_loss_trace.png", cache_timeout=0, as_attachment=True)
        return response
    except Exception as e:
        return jsonify({"code": 500,
                        "message": "{} Maybe you algorithm is still running or its result was wrong. You can rerun your code to generate graph.".format(
                            e)})


@graph_bp.route("/get_throughput_graph/<task_id>", methods=["GET"])
def return_throughput_graph(task_id):
    directory = "/home/liuwei/Transhub_data/cc_training/{}/sourdough/datagrump/result/".format(task_id)
    try:
        response = send_file(directory + "throughput.png", cache_timeout=0, as_attachment=True)
        return response
    except Exception as e:
        return jsonify({"code": 500,
                        "message": "{} Maybe you algorithm is still running or its result was wrong. You can rerun your code to generate graph.".format(
                            e)})


@graph_bp.route("/get_delay_graph/<task_id>", methods=["GET"])
def return_delay_graph(task_id):
    directory = "/home/liuwei/Transhub_data/cc_training/{}/sourdough/datagrump/result/".format(task_id)
    try:
        response = send_file(directory + "delay.png", cache_timeout=0, as_attachment=True)
        return response
    except Exception as e:
        return jsonify({"code": 500,
                        "message": "{} Maybe you algorithm is still running or its result was wrong. You can rerun your code to generate graph.".format(
                            e)})
