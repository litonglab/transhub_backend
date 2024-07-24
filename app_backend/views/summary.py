from flask import Blueprint, request

from app_backend.model.Rank_model import Rank_model
from app_backend.security.safe_check import check_user_state
from app_backend.vo.response import myResponse

summary_bp = Blueprint('summary', __name__)


# @summary_bp.route("/get_summary_pdf/<user_id>", methods=["GET"])
# def return_summary(user_id):
#     if not user_id:
#         return {"code": 400, "message": "Bad request!"}
#     real_info = User_model.query.get(user_id)
#     if not real_info:
#         return {"code": 400, "message": "Real info need be completed!"}
#     temp_class = real_info[1]
#     if temp_class == ALL_CLASS[0]:
#         temp_dir = ALL_CLASS_PATH[0]
#     elif temp_class == ALL_CLASS[1]:
#         temp_dir = ALL_CLASS_PATH[1]
#     else:
#         temp_dir = ALL_CLASS_PATH[2]
#     print(temp_dir)
#     pdf_filenames = [f"{temp_dir}/src/experiments/data/pantheon_summary.pdf",
#                      f"{temp_dir}/src/experiments/data_p/pantheon_summary.pdf"]
#     merger = PyPDF2.PdfMerger()
#     for pdf_filename in pdf_filenames:
#         merger.append(PyPDF2.PdfReader(pdf_filename))
#     merger.write(f"{temp_dir}/merged_summary.pdf")
#     return send_file(f"{temp_dir}/merged_summary.pdf", cache_timeout=0, as_attachment=True)


@summary_bp.route("/get_ranks", methods=["POST"])
def return_ranks():
    user_id = request.json.get('user_id')
    if not check_user_state(user_id):
        return myResponse(200, "Please login firstly!")
    ranks = Rank_model.query.all()
    res = []
    # 按照task_score排序, 降序
    ranks = sorted(ranks, key=lambda x: x.task_score, reverse=True)
    for rank in ranks:
        res.append(rank.to_dict())
    return myResponse(200, "Success", rank=res)



# @summary_bp.route("/get_loss_summary_svg", methods=["GET"])
# def return_loss_summary_svg():
#     return send_file("/home/liuwei/pantheon/src/experiments/data_p/pantheon_summary.svg", cache_timeout=0,
#                      as_attachment=True)
#
#
# @summary_bp.route("/get_loss_summary_pdf", methods=["GET"])
# def return_loss_summary():
#     return send_file("/home/liuwei/pantheon/src/experiments/data_p/pantheon_summary.pdf", cache_timeout=0,
#                      as_attachment=True)
#
#
# @summary_bp.route("/get_summary_svg", methods=["GET"])
# def return_summary_svg():
#     return send_file("/home/liuwei/pantheon/src/experiments/data/pantheon_summary.svg", cache_timeout=0,
#                      as_attachment=True)
