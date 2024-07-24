from flask import  send_file, Blueprint, request
from app_backend.config import cctraining_config
from app_backend.vo.response import myResponse

help_bp = Blueprint('help', __name__)


@help_bp.route("/get_cca_guide", methods=["POST"])
def return_cca_file():
    cname = request.json['cname']
    if cname == cctraining_config.cname:
        return send_file(cctraining_config.cca_guide_path, as_attachment=True)
    else:
        return myResponse(400, "No cca guide found.")


@help_bp.route("/get_user_guide", methods=["POST"])
def return_guide_file():
    cname = request.json['cname']
    if cname == cctraining_config.cname:
        return send_file(cctraining_config.user_guide_path, as_attachment=True)
    else:
        return myResponse(400, "No user guide found.")

@help_bp.route("/get_zhinan", methods=["POST"])
def return_zhinan():
    cname = request.json['cname']
    if cname == cctraining_config.cname:
        return send_file(cctraining_config.zhinan_path, as_attachment=True)
    else:
        return myResponse(400, "No guide found.")
