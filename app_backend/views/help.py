import time
import logging

from flask import send_file, Blueprint, current_app
from flask_jwt_extended import jwt_required, get_jwt

from app_backend import ALL_CLASS
from app_backend.config import CNAME_LIST
from app_backend.vo import HttpResponse

help_bp = Blueprint('help', __name__)
logger = logging.getLogger(__name__)


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
    
    config = ALL_CLASS[cname]
    if config:
        logger.info(f"Sending tutorial file: {config['zhinan_path']}")
        return send_file(config['zhinan_path'], as_attachment=True)
        # return send_file(config.zhinan_path, mimetype="application/pdf")
    else:
        logger.warning(f"Tutorial not found for competition {cname}")
        return HttpResponse.fail("No such tutorial!")


@help_bp.route('/help_get_pantheon', methods=["GET"])
def return_pantheon():
    return HttpResponse.ok(pantheon=CNAME_LIST)


@help_bp.route("/help_get_competition_time", methods=["GET"])
@jwt_required()
def return_competition_time():
    """ Returns the start and end time of the competition for the current user.
    """
    cname = get_jwt().get('cname')
    logger.debug(f"Competition time request for {cname}")
    
    config = ALL_CLASS[cname]
    time_stmp = [int(time.mktime(time.strptime(config['start_time'], "%Y-%m-%d-%H-%M-%S"))),
                 int(time.mktime(time.strptime(config['end_time'], "%Y-%m-%d-%H-%M-%S")))]
    logger.debug(f"Competition time for {cname}: start={config['start_time']}, end={config['end_time']}")
    return HttpResponse.ok(data=time_stmp)
