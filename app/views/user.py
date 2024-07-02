import uuid

from flask import Blueprint, request, jsonify, session

from app.model.User_model import User_model
from app.vo.response import myResponse
from app.security.safe_check import check_user_state

user_bp = Blueprint('user', __name__)


@user_bp.route('/user_login', methods=['POST'])
def user_login():
    request_data = request.json or request.form
    username = request_data['username']
    password = request_data['password']
    user = User_model.query.filter_by(username=username, password=password).first()
    if not user:
        return myResponse(400, "User not found or Username error or Password error.")
    session['user_id'] = user.user_id
    return myResponse(200, "Login success.", user_id=user.user_id)


@user_bp.route('/user_logout', methods=['POST'])
def user_logout():
    if not check_user_state(request.json['user_id']):
        return myResponse(400, "Please login firstly.")
    user_id = request.json['user_id']
    if user_id != session.get('user_id'):
        return {"code": 400, "message": "Please login firstly."}
    session.pop('user_id', None)
    return {"code": 200, "message": "Logout success."}


@user_bp.route('/user_register', methods=['POST'])
def user_register():
    try:
        request_data = request.json or request.form
        username = request_data['username']
        password = request_data['password']
        real_name = request_data['real_name']
        sno = request_data['sno']
        # 检测username，real_name,sno是否已经存在
        user = User_model(username=username, password=password, real_name=real_name, sno=sno)
        if user.is_exist():
            return myResponse(400, "User already exists.")
        elif user.is_null_info():
            return myResponse(400, "Information is not complete.")
        elif not str(sno).isdecimal() or len(sno) != 10:
            return myResponse(400, "Please input correct student number(10 numbers)!")
        else:
            user_id = str(uuid.uuid1())
            user.user_id = user_id
            user.save()
            return myResponse(200, "Register success.", user_id=user_id)
    except Exception as e:
        print("register occur error: {}".format(e))
        return myResponse(500, "Register failed.")


@user_bp.route("/change_password", methods=['POST'])
def change_password():
    request_data = request.json or request.form
    user_id = request_data['user_id']
    new_pwd = request_data['new_pwd']
    if not check_user_state(user_id):
        return myResponse(400, "Please login firstly.")

    user = User_model.query.filter_by(user_id=user_id).first()
    user.password = new_pwd
    user.save()
    return myResponse(200, "Change password success.")



# app/views/user.py
@user_bp.route("/get_real_info/<user_id>", methods=["GET"])
def return_real_info(user_id):
    if not check_user_state(user_id):
        return myResponse(400, "Please login firstly.", real_info=None)
    user = User_model.query.filter_by(user_id=user_id).first()
    real_info = {"real_name": user.real_name, "sno": user.sno}
    return myResponse(200, "Get real info success.", real_info=real_info)


# app/views/user.py
@user_bp.route("/set_real_info", methods=["POST"])
def change_real_info():

    user_id = request.json['user_id']
    real_name = request.json['real_name']
    sno = request.json['sno']

    if not check_user_state(user_id):
        return myResponse(400, "Please login firstly.")
    user = User_model.query.filter_by(user_id=user_id).first()
    if not user:
        return myResponse(400, "User not found.")
    if not real_name or not sno:
        return myResponse(400, "Real info need to be provided completely.")
    user.update_real_info(real_name, sno)
    return myResponse(200, "Set real info success.")


