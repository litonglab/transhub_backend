from flask import Blueprint, jsonify

from app.models import query_history_records

history_bp = Blueprint('history', __name__)


@history_bp.route("/get_history_records/<user_id>", methods=["GET"])
def return_history_records(user_id):
    history_records = query_history_records(user_id)
    if not history_records:
        return jsonify({"code": 500, "message": "Maybe you never submit a record, you can submit your code now!"})
    history_info = [{"task_id": record[0], "user_id": record[1], "task_status": record[2], "task_score": record[3],
                     "running_port": record[4], "cca_name": record[5], "created_time": record[6],
                     "score_without_loss": record[7], "score_with_loss": record[8]} for record in history_records]
    return jsonify({"code": 200, "history_records": history_info})
