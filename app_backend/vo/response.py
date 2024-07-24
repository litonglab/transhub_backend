from flask import jsonify


def myResponse(code='400', message='', **kwargs):
    response = {
        'code': code,
        'message': message
    }
    response.update(kwargs)
    return jsonify(response)
