from flask import send_file, Blueprint, request
from flask_jwt_extended import jwt_required

from app_backend.config import get_config_by_cname, ALL_CLASS
from app_backend.vo.response import myResponse

help_bp = Blueprint('help', __name__)


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


@help_bp.route("/help_get_tutorial", methods=["POST"])
@jwt_required()
def return_zhinan():
    cname = request.json['cname']
    config = get_config_by_cname(cname)
    if config:
        return send_file(config.zhinan_path, as_attachment=True)
        # return send_file(config.zhinan_path, mimetype="application/pdf")
    else:
        return myResponse(400, "No guide found.")


@help_bp.route('/help_get_pantheon', methods=["POST"])
def return_pantheon():
    return myResponse(200, "success", pantheon=[cname for cname, path in ALL_CLASS.items()])
