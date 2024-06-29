import uuid

from flask import Blueprint, request, jsonify

from app.model.User_model import insert_user_item, query_user, query_real_info, update_real_info, query_pwd, exist_user, \
    change_user_item, is_null, is_null_info, is_existed

user_bp = Blueprint('user', __name__)


@user_bp.route('/user_login', methods=['POST'])
def user_login():
    request_data = request.json or request.form
    username = request_data['username']
    password = request_data['password']
    if is_null(username, password):
        login_massage = "温馨提示：账号密码是必填"
        return {"code": 400, "message": login_massage}
    elif is_existed(username, password):
        user_id = query_user(username, password)
        return {"code": 200, "message": "登录成功！", "user_id": user_id}
    elif exist_user(username):
        login_massage = "温馨提示：密码错误，请输入正确密码"
        return {"code": 400, "message": login_massage}
    else:
        login_massage = "温馨提示：用户尚未注册，请点击注册"
        return {"code": 400, "message": login_massage}


@user_bp.route('/user_register', methods=['POST'])
def user_register():
    try:
        request_data = request.json or request.form
        username = request_data['username']
        password = request_data['password']
        real_name = request_data['real_name']
        sno = request_data['sno']
        Sclass = request_data['Sclass']
        user_id = uuid.uuid1()
        if exist_user(username):
            message = "该用户名已被占用！"
            return {"code": 400, "message": message}
        elif is_null_info(real_name, sno, Sclass):
            message = "温馨提示：真实信息是必填"
            return {"code": 400, "message": message}
        elif not str(sno).isdecimal() or len(sno) != 10:
            message = "温馨提示：请输入10位数字学号"
            return {"code": 400, "message": message}
        else:
            insert_user_item(user_id, username, password, '0', real_name, Sclass, sno)
            message = "注册成功！请返回登录页面"
            return {"code": 200, "message": message, "user_id": user_id}
    except Exception as e:
        print("register occur error: {}".format(e))
        return {"code": 500, "message": "Register occur ERROR!"}


@user_bp.route("/change_password", methods=['POST'])
def change_password():
    request_data = request.json or request.form
    user_id = request_data['user_id']
    new_pwd = request_data['new_pwd']
    change_user_item(user_id, new_pwd)
    message = "修改密码成功！"
    return {"code": 200, "message": message}

# app/views/user.py
@user_bp.route("/get_real_info/<user_id>",methods=["GET"])
def return_real_info(user_id):
    real_record = query_real_info(user_id)
    if not real_record:
        return jsonify({"code": 500, "message": "Error in query real info!"})
    print(real_record)
    real_info = {"real_name":real_record[0], "myclass":real_record[1], "sno":real_record[2]}
    return jsonify({"code":200, "real_info":real_info})

# app/views/user.py
@user_bp.route("/set_real_info/<user_id>",methods=["GET"])
def change_real_info(user_id):
    new_real_record = request.args
    if not new_real_record:
        return jsonify({"code": 400, "message": "Real info need to be provided!"})
    if not new_real_record.get("real_name") or not new_real_record.get("myclass") or not new_real_record.get("sno"):
        return jsonify({"code": 400, "message": "Real info is not complete!"})
    if not str(new_real_record.get("sno")).isdecimal() or len(new_real_record.get("sno")) != 10:
        message = "Please input correct student number(ten numbers)!"
        return {"code": 400, "message": message}
    update_real_info(user_id, new_real_record.get("real_name"), new_real_record.get("myclass"), new_real_record.get("sno"))
    return jsonify({"code":200, "message": "Update real info success."})

@user_bp.route("/get_old_pwd/<user_id>",methods=["GET"])
def return_old_pwd(user_id):
    old_pwd = query_pwd(user_id)
    if not old_pwd:
        return jsonify({"code": 500, "message": "Error in query old password!"})
    data = old_pwd[0]
    return jsonify({"code": 200, "data": data})
