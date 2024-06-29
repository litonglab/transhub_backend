import os

from flask import jsonify, make_response, send_from_directory, Blueprint

from app.model.Task_model import query_task


log_bp = Blueprint('log', __name__)

@log_bp.route("/get_log/<task_id>",methods=["GET"])
def return_log(task_id):
    task_info = query_task(task_id)
    if not task_info:
        return jsonify({"code": 500, "message": "Maybe task {} is not running, you can rerun your code to generate it.".format(task_id)})
    cca_name = task_info[5]
    log_name = task_id+'_throughput.txt'
    result_directory = "/home/liuwei/Transhub_data/cc_training/{}/sourdough/datagrump/result/".format(task_id)
    if os.path.exists(result_directory+task_id+'_throughput.txt'):
        directory = result_directory
    else:
        # no finished normally
        directory = "/home/liuwei/Transhub_data/cc_training/log/"
        log_name = "{}_logfile.txt".format(cca_name)
    try:
        response = make_response(
                send_from_directory(directory, log_name, as_attachment=True))
        return response
    except Exception as e:
        return jsonify({"code": 404, "message": "{}".format(e)})
