from flask import Blueprint

# from app.model.User_model import User_model
from app.model.Task_model import Task_model
from app.security.safe_check import check_user_state
from app.vo.response import myResponse

history_bp = Blueprint('history', __name__)


@history_bp.route("/get_history_records/<user_id>", methods=["GET"])
def return_history_records(user_id):
    if not check_user_state(user_id):
        return myResponse(400, "Please login firstly.")
    history_records = Task_model.query.filter_by(user_id=user_id).all()
    records = [r.to_dict() for r in history_records]

    return myResponse(400, "Success", history=records)
