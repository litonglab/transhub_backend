import logging
import uuid

from flask import Blueprint, make_response
from flask_jwt_extended import create_access_token, set_access_cookies, unset_jwt_cookies, jwt_required, \
    get_jwt_identity, get_jwt

from app_backend import get_default_config
from app_backend.model.competition_model import CompetitionModel
from app_backend.model.user_model import UserModel
from app_backend.validators.decorators import validate_request, get_validated_data
from app_backend.validators.schemas import UserLoginSchema, UserRegisterSchema, ChangePasswordSchema, \
    UserChangeRealInfoSchema
from app_backend.vo.http_response import HttpResponse

user_bp = Blueprint('user', __name__)
logger = logging.getLogger(__name__)
config = get_default_config()


@user_bp.route('/user_login', methods=['POST'])
@validate_request(UserLoginSchema)
def user_login():
    data = get_validated_data(UserLoginSchema)
    username = data.username
    password = data.password
    cname = data.cname

    logger.debug(f"User login attempt: username={username}, cname={cname}")

    user = UserModel.query.filter_by(username=username, password=password).first()
    if not user:
        logger.warning(f"Login failed: User not found or credentials invalid for username={username}")
        return HttpResponse.fail("用户名或密码错误，请检查后重新输入。")
    # 参赛
    # 检测用户是否已经参加了比赛
    # 判断cname是否存在配置文件中
    if cname not in config.Course.CNAME_LIST:
        logger.warning(f"Login failed: Invalid competition name {cname}")
        return HttpResponse.not_found("该课程（比赛）不存在，请重试。")

    class_student_list = config.Course.ALL_CLASS[cname]['student_list']
    if len(class_student_list) > 0 and user.sno not in class_student_list:
        logger.warning(f"Login failed: Student {user.sno} not in class list for {cname}")
        return HttpResponse.fail("该学号不在此课程（比赛）的名单中，请确认你已选课或报名竞赛。")
    if CompetitionModel.query.filter_by(user_id=user.user_id, cname=cname).first():
        logger.info(f"User {username} successfully logged in to {cname}")
        # 生成带自定义内容的JWT
        additional_claims = {"cname": cname}
        access_token = create_access_token(identity=user.user_id, additional_claims=additional_claims)
        resp = make_response(HttpResponse.ok(user_id=user.user_id))
        set_access_cookies(resp, access_token, max_age=config.Security.JWT_ACCESS_TOKEN_EXPIRES)
        return resp
    else:
        # 更新：在编译目录统一使用公共目录后，实际上此逻辑已不再必要，这里保留下来作为首次登录的欢迎界面
        # 异步调用参赛函数，为用户报名
        # @copy_current_request_context
        # def async_participate():
        #     user.participate_competition(cname)
        # executor.submit(async_participate)
        user.participate_competition(cname)
        message = "同学你好，欢迎加入【{}】课程（比赛），首次加入课程（比赛），系统需要后台为你创建项目工程，预计需要数秒钟，请稍后再登录。".format(
            cname)
        logger.info(f"New user {username} initiated participation in {cname}")
        return HttpResponse.error(201, message)


@user_bp.route('/user_logout', methods=['GET'])
def user_logout():
    logger.debug("User logout request received")
    resp = make_response(HttpResponse.ok())
    unset_jwt_cookies(resp)
    return resp


@user_bp.route('/user_register', methods=['POST'])
@validate_request(UserRegisterSchema)
def user_register():
    try:
        data = get_validated_data(UserRegisterSchema)
        username = data.username
        password = data.password
        real_name = data.real_name
        sno = data.sno

        logger.debug(f"Registration attempt for user: username={username}, real_name={real_name}, sno={sno}")

        # 检测username，sno是否已经存在
        user = UserModel(username=username, password=password, real_name=real_name, sno=sno)
        if user.is_exist():
            logger.warning(f"Registration failed: Username {username} already exists")
            return HttpResponse.fail("此用户名或学号已被注册，请更换用户名或学号。")
        else:
            user_id = str(uuid.uuid1())
            user.user_id = user_id
            user.save()
            logger.info(f"User {username} successfully registered with ID {user_id}")
            return HttpResponse.ok("注册成功", user_id=user_id)
    except Exception as e:
        logger.error(f"Registration error: {str(e)}", exc_info=True)
        return HttpResponse.internal_error()


@user_bp.route("/user_change_password", methods=['POST'])
@jwt_required()
@validate_request(ChangePasswordSchema)
def change_password():
    data = get_validated_data(ChangePasswordSchema)
    user_id = get_jwt_identity()  # 用户id
    old_pwd = data.old_pwd
    new_pwd = data.new_pwd

    logger.debug(f"Password change attempt for user_id={user_id}")

    user = UserModel.query.filter_by(user_id=user_id, password=old_pwd).first()
    if not user:
        logger.warning(f"Password change failed: Invalid old password for user_id={user_id}")
        return HttpResponse.fail("旧密码错误，请检查后重新输入。")

    user.password = new_pwd
    user.save()
    logger.info(f"Password successfully changed for user_id={user_id}")
    return HttpResponse.ok("修改密码成功")


@user_bp.route("/user_get_real_info", methods=["GET"])
@jwt_required()
def return_real_info():
    user_id = get_jwt_identity()
    logger.debug(f"Fetching real info for user_id={user_id}")

    user = UserModel.query.filter_by(user_id=user_id).first()
    real_info = {"cname": get_jwt().get('cname'),
                 "real_name": user.real_name,
                 "sno": user.sno}
    return HttpResponse.ok(real_info=real_info)


@user_bp.route("/user_check_login", methods=["GET"])
@jwt_required()
def check_login():
    user_id = get_jwt_identity()
    logger.debug(f"Login check for user_id={user_id}")
    return HttpResponse.ok()


@user_bp.route("/user_set_real_info", methods=["POST"])
@jwt_required()
@validate_request(UserChangeRealInfoSchema)
def change_real_info():
    user_id = get_jwt_identity()
    data = get_validated_data(UserChangeRealInfoSchema)
    real_name = data.real_name

    logger.info(f"Updating real info for user_id={user_id}, new real_name={real_name}")

    user = UserModel.query.filter_by(user_id=user_id).first()
    user.update_real_info(real_name)
    logger.info(f"Successfully updated real info for user_id={user_id}")
    return HttpResponse.ok("修改个人信息成功")
