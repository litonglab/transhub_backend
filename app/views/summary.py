from flask import Blueprint, request, send_file, jsonify
import PyPDF2

from app.config import ALL_SUMMARY_DIR
from app.model.User_model import query_real_info
from app.models import *


summary_bp = Blueprint('summary', __name__)


@summary_bp.route("/get_summary_pdf/<user_id>", methods=["GET"])
def return_summary(user_id):
    if not user_id:
        return {"code": 400, "message": "Bad request!"}
    real_info = query_real_info(user_id)
    if not real_info:
        return {"code": 400, "message": "Real info need be completed!"}
    temp_class = real_info[1]
    if temp_class == ALL_CLASS[0]:
        temp_dir = ALL_SUMMARY_DIR[0]
    elif temp_class == ALL_CLASS[1]:
        temp_dir = ALL_SUMMARY_DIR[1]
    else:
        temp_dir = ALL_SUMMARY_DIR[2]
    print(temp_dir)
    pdf_filenames = [f"{temp_dir}/src/experiments/data/pantheon_summary.pdf",
                     f"{temp_dir}/src/experiments/data_p/pantheon_summary.pdf"]
    merger = PyPDF2.PdfMerger()
    for pdf_filename in pdf_filenames:
        merger.append(PyPDF2.PdfReader(pdf_filename))
    merger.write(f"{temp_dir}/merged_summary.pdf")
    return send_file(f"{temp_dir}/merged_summary.pdf", cache_timeout=0, as_attachment=True)


@summary_bp.route("/get_ranks", methods=["GET"])
def return_ranks():
    user_id = request.args.get("user_id")
    if not user_id:
        return {"code": 400, "message": "Bad request!"}
    real_info = query_real_info(user_id)
    if real_info[1] in ALL_CLASS:
        rank_list = query_rank_list(real_info[1])
    else:
        rank_list = query_rank_list()
    if not rank_list:
        return jsonify({"code": 500, "message": "Maybe no task has finished, you can rerun your code to generate it."})
    # task_res = {"task_id": task_info[0], "user_id": task_info[1], "task_status": task_info[2], "task_score": task_info[3], "running_port": task_info[4]}
    ranks_info = [
        {"task_id": rank[0], "user_id": rank[1], "username": rank[2], "cca_name": rank[3], "task_score": rank[4],
         "created_time": rank[5], "score_without_loss": rank[6], "score_with_loss": rank[7]} for rank in rank_list]
    if request.args and request.args.get("order") == "asc":
        ranks_info = [
            {"task_id": rank[0], "user_id": rank[1], "username": rank[2], "cca_name": rank[3], "task_score": rank[4],
             "created_time": rank[5], "score_without_loss": rank[6], "score_with_loss": rank[7]} for rank in
            reversed(rank_list)]
    return jsonify({"code": 200, "rank_list": ranks_info})


@summary_bp.route("/get_loss_summary_svg", methods=["GET"])
def return_loss_summary_svg():
    return send_file("/home/liuwei/pantheon/src/experiments/data_p/pantheon_summary.svg", cache_timeout=0,
                     as_attachment=True)


@summary_bp.route("/get_loss_summary_pdf", methods=["GET"])
def return_loss_summary():
    return send_file("/home/liuwei/pantheon/src/experiments/data_p/pantheon_summary.pdf", cache_timeout=0,
                     as_attachment=True)


@summary_bp.route("/get_summary_svg", methods=["GET"])
def return_summary_svg():
    return send_file("/home/liuwei/pantheon/src/experiments/data/pantheon_summary.svg", cache_timeout=0,
                     as_attachment=True)
