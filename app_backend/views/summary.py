import logging

from flask import Blueprint
from flask_jwt_extended import jwt_required, get_jwt, current_user

from app_backend import cache
from app_backend.model.rank_model import RankModel
from app_backend.model.user_model import UserModel
from app_backend.vo.http_response import HttpResponse

summary_bp = Blueprint('summary', __name__)
logger = logging.getLogger(__name__)


def _build_rank_dict(upload_id, username, task_score, algorithm, upload_time, sno=None, real_name=None):
    """构建排名字典的辅助函数，复用to_dict()的结构"""
    rank_dict = {
        'upload_id': upload_id,
        'username': username,
        'task_score': task_score,
        'algorithm': algorithm,
        'upload_time': upload_time
    }

    # 如果提供了学号和真实姓名，添加admin字段
    if sno is not None:
        rank_dict['to_admin'] = {
            'sno': sno,
            'real_name': real_name
        }

    return rank_dict


@cache.memoize(timeout=10)
def get_ranks_for_competition(cname, is_admin=False):
    """获取比赛榜单的缓存函数"""
    if is_admin:
        # admin用户：使用JOIN查询一次性获取榜单和用户信息
        ranks_with_users = RankModel.query.join(
            UserModel, RankModel.user_id == UserModel.user_id
        ).filter(RankModel.cname == cname).with_entities(
            RankModel.upload_id,
            RankModel.user_id,
            RankModel.task_score,
            RankModel.algorithm,
            RankModel.upload_time,
            RankModel.username,
            UserModel.sno,
            UserModel.real_name
        ).all()

        logger.debug(f"query {len(ranks_with_users)} ranks with user info for competition {cname}")

        result = []
        for rank_data in ranks_with_users:
            rank_dict = _build_rank_dict(
                rank_data.upload_id,
                rank_data.username,
                rank_data.task_score,
                rank_data.algorithm,
                rank_data.upload_time,
                rank_data.sno,  # 传入学号
                rank_data.real_name  # 传入真实姓名
            )
            result.append(rank_dict)

        return result
    else:
        # 普通用户：只查询榜单信息，复用原有的to_dict()方法
        ranks = RankModel.query.filter_by(cname=cname).all()
        logger.debug(f"query {len(ranks)} ranks for competition {cname}")
        return [rank.to_dict() for rank in ranks]


@summary_bp.route("/summary_get_ranks", methods=["GET"])
@jwt_required()
def return_ranks():
    cname = get_jwt().get('cname')
    logger.debug(f"Rank request for competition {cname}")

    # 判断当前用户是否为admin
    is_admin = current_user.is_admin()
    logger.debug(f"User is admin: {is_admin}, return more rank info.")

    ranks = get_ranks_for_competition(cname, is_admin)
    logger.debug(f"Returning {len(ranks)} ranks for competition {cname}")
    return HttpResponse.ok(rank=ranks)
