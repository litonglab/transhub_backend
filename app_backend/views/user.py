import uuid
from concurrent.futures import ThreadPoolExecutor

from flask import Blueprint, request, make_response, copy_current_request_context
from flask_jwt_extended import create_access_token, set_access_cookies, unset_jwt_cookies, jwt_required, \
    get_jwt_identity, get_jwt

from app_backend.config import cname_list
from app_backend.decorators.validators import validate_request
from app_backend.model.Competition_model import Competition_model
from app_backend.model.User_model import User_model
from app_backend.validators.schemas import UserLoginSchema, UserRegisterSchema, ChangePasswordSchema
from app_backend.vo import HttpResponse

# 创建线程池执行器
executor = ThreadPoolExecutor(2)

user_bp = Blueprint('user', __name__)


@user_bp.route('/user_login', methods=['POST'])
@validate_request(UserLoginSchema)
def user_login():
    data = request.validated_data
    username = data.username
    password = data.password
    cname = data.cname

    user = User_model.query.filter_by(username=username, password=password).first()
    if not user:
        return HttpResponse.error("User not found or Username error or Password error.")
    # 参赛
    # 检测用户是否已经参加了比赛
    # 判断cname是否存在配置文件中
    if cname not in cname_list:
        return HttpResponse.error("Competition not found or cname error.")
    if Competition_model.query.filter_by(user_id=user.user_id, cname=cname).first():
        # 生成带自定义内容的JWT
        additional_claims = {"cname": cname}
        access_token = create_access_token(identity=user.user_id, additional_claims=additional_claims)
        resp = make_response(HttpResponse.ok(user_id=user.user_id))
        set_access_cookies(resp, access_token)
        return resp
    else:
        # 异步调用参赛函数，为用户报名
        # user.paticapate_competition(cname)
        # 用 copy_current_app_context 包装你的函数
        # todo: 加锁，用户频繁操作可能导致重复调用此函数
        @copy_current_request_context
        def async_paticapate():
            user.paticapate_competition(cname)

        executor.submit(async_paticapate)
        message = "验证成功，欢迎参加【{}】课程，首次加入课程，系统后台需要为你创建项目工程，预计需要几分钟，请稍后再登录。\n如果长时间仍无法登录，请联系管理员。".format(
            cname)
        return HttpResponse.error(201, message)


@user_bp.route('/user_logout', methods=['GET'])
def user_logout():
    resp = make_response(HttpResponse.ok())
    unset_jwt_cookies(resp)
    return resp


@user_bp.route('/user_register', methods=['POST'])
@validate_request(UserRegisterSchema)
def user_register():
    try:
        data = request.validated_data
        username = data.username
        password = data.password
        real_name = data.real_name
        sno = data.sno

        # 检测username，real_name,sno是否已经存在
        user = User_model.query.filter_by(real_name=real_name, sno=sno).first()
        if user:
            return HttpResponse.error("User already exists.")
        user = User_model(username=username, password=password, real_name=real_name, sno=sno)
        if user.is_exist():
            return HttpResponse.error("User already exists.")
        elif user.is_null_info():
            return HttpResponse.error("Information is not complete.")
        else:
            user_id = str(uuid.uuid1())
            user.user_id = user_id
            user.save()
            return HttpResponse.ok("Register success.", user_id=user_id)
    except Exception as e:
        print("register occur error: {}".format(e))
        return HttpResponse.error(500, "Register failed.")


@user_bp.route("/user_change_password", methods=['POST'])
@jwt_required()
@validate_request(ChangePasswordSchema)
def change_password():
    data = request.validated_data
    user_id = data.user_id
    old_pwd = data.oldpwd
    new_pwd = data.new_pwd

    user = User_model.query.filter_by(user_id=user_id, password=old_pwd).first()
    if not user:
        return HttpResponse.error("Password error.")

    user.password = new_pwd
    user.save()
    return HttpResponse.ok("Change password success.")


@user_bp.route("/user_get_real_info", methods=["POST"])
@jwt_required()
def return_real_info():
    user_id = get_jwt_identity()
    user = User_model.query.filter_by(user_id=user_id).first()
    real_info = {"cname": get_jwt().get('cname'),
                 "real_name": user.real_name,
                 "sno": user.sno}
    return HttpResponse.ok("Get real info success.", real_info=real_info)


@user_bp.route("/user_check_login", methods=["GET"])
@jwt_required()
def check_login():
    return HttpResponse.ok()
# @user_bp.route("/user_set_real_info", methods=["POST"])
# @jwt_required()
# def change_real_info():
#     user_id = get_jwt_identity()
#     real_name = request.json['real_name']
#     sno = request.json['sno']
#     user = User_model.query.filter_by(user_id=user_id).first()
#     if not user:
#         return myResponse(400, "User not found.")
#     if not real_name or not sno:
#         return myResponse(400, "Real info need to be provided completely.")
#     user.update_real_info(real_name, sno)
#     return myResponse(200, "Set real info success.")
