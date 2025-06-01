from flask import Blueprint
from flask_jwt_extended import jwt_required, get_jwt

from app_backend.model.Rank_model import Rank_model
from app_backend.vo.response import myResponse

summary_bp = Blueprint('summary', __name__)


@summary_bp.route("/summary_get_ranks", methods=["GET"])
@jwt_required()
def return_ranks():
    cname = get_jwt().get('cname')
    ranks = Rank_model.query.filter_by(cname=cname).all()
    res = []
    # 按照task_score排序, 降序
    ranks = sorted(ranks, key=lambda x: x.task_score, reverse=True)
    for rank in ranks:
        res.append(rank.to_dict())
    return myResponse(200, "Success", rank=res)
