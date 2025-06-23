import logging
import os
import time

from flask import Blueprint
from flask_jwt_extended import jwt_required, get_jwt

from app_backend import get_default_config
from app_backend.vo.http_response import HttpResponse

help_bp = Blueprint('help', __name__)
logger = logging.getLogger(__name__)
config = get_default_config()


# @help_bp.route("/help_get_cca_guide", methods=["POST"])
# def return_cca_file():
#     cname = request.json['cname']
#     if cname == cctraining_config.cname:
#         return send_file(cctraining_config.cca_guide_path, as_attachment=True)
#     else:
#         return myResponse(400, "No cca guide found.")
#
#
# @help_bp.route("/get_user_guide", methods=["POST"])
# def return_guide_file():
#     cname = request.json['cname']
#     if cname == cctraining_config.cname:
#         return send_file(cctraining_config.user_guide_path, as_attachment=True)
#     else:
#         return myResponse(400, "No user guide found.")


@help_bp.route("/help_get_tutorial", methods=["GET"])
@jwt_required()
def return_zhinan():
    cname = get_jwt().get('cname')
    logger.debug(f"Tutorial request for competition {cname}")

    _config = config.Course.ALL_CLASS[cname]
    if _config and os.path.exists(_config['zhinan_path']):
        logger.info(f"Sending tutorial file: {_config['zhinan_path']}")
        return HttpResponse.send_attachment_file(_config['zhinan_path'])
    else:
        logger.error(f"Tutorial not found for competition {cname}")
        return HttpResponse.not_found("文档不存在")


@help_bp.route('/help_get_pantheon', methods=["GET"])
def return_pantheon():
    return HttpResponse.ok(pantheon=config.Course.CNAME_LIST)


@help_bp.route("/help_get_competition_time", methods=["GET"])
@jwt_required()
def return_competition_time():
    """ Returns the start and end time of the competition for the current user.
    """
    cname = get_jwt().get('cname')
    logger.debug(f"Competition time request for {cname}")

    _config = config.Course.ALL_CLASS[cname]
    time_stmp = [int(time.mktime(time.strptime(_config['start_time'], "%Y-%m-%d %H:%M:%S"))),
                 int(time.mktime(time.strptime(_config['end_time'], "%Y-%m-%d %H:%M:%S")))]
    logger.debug(f"Competition time for {cname}: start={_config['start_time']}, end={_config['end_time']}")
    return HttpResponse.ok(data=time_stmp)
