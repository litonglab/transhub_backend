import os

from flask import jsonify, make_response, send_from_directory, Blueprint

from app.model.Task_model import Task_model

source_code_bp = Blueprint('app', __name__)

@source_code_bp.route("/get_source_code/<task_id>",methods=["GET"])
def return_code(task_id):
    task_info = Task_model.query.filter_by(task_id=task_id).first()
    print(task_info)
    if not task_info or len(task_info)<7:
        return jsonify({"code": 500, "message": "Maybe task {} is not running, you can rerun your code to generate it.".format(task_id)})
    cca_name = task_info[5] or ''
    result_directory = "/home/liuwei/Transhub_data/cc_training/{}/sourdough/datagrump/result/".format(task_id)
    if os.path.exists(result_directory+cca_name+'.cc'):
        directory = result_directory
    else:
        # no finished normally
        directory = "/home/liuwei/Transhub_data/cc_training/{}/sourdough/datagrump/".format(task_id)
        cca_name = "controller"
    try:
        response = make_response(
                send_from_directory(directory, cca_name+'.cc', as_attachment=True))
        return response
    except Exception as e:
        return jsonify({"code": 404, "message": "{}".format(e)})