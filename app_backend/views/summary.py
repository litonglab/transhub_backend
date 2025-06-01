from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app_backend.model.Rank_model import Rank_model
from app_backend.vo.response import myResponse

summary_bp = Blueprint('summary', __name__)


@summary_bp.route("/summary_get_ranks", methods=["POST"])
@jwt_required()
def return_ranks():
    user_id = get_jwt_identity()
    cname = request.json.get('cname')
    ranks = Rank_model.query.filter_by(cname=cname).all()
    res = []
    # 按照task_score排序, 降序
    ranks = sorted(ranks, key=lambda x: x.task_score, reverse=True)
    for rank in ranks:
        res.append(rank.to_dict())
    return myResponse(200, "Success", rank=res)
