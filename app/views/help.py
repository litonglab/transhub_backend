from flask import send_from_directory, send_file, Blueprint

help_bp = Blueprint('help', __name__)


@help_bp.route("/get_help/cca_guide", methods=["GET"])
def return_cca_file():
    return send_from_directory("/home/liuwei/Transhub/help/", 'cca_guide.docx', as_attachment=True)


@help_bp.route("/get_help/user_guide", methods=["GET"])
def return_guide_file():
    return send_from_directory("/home/liuwei/Transhub/help/", 'user_guide.docx', as_attachment=True)


@help_bp.route("/get_zhinan", methods=["GET"])
def return_zhinan():
    return send_file("/home/liuwei/zhinan.pdf", cache_timeout=0, as_attachment=True)
