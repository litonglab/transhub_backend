from flask import jsonify


def _my_response(code=400, message='', **kwargs):
    response = {
        'code': code,
        'message': message
    }
    response.update(kwargs)
    return jsonify(response)


def ok(message='success', **kwargs):
    """
    Returns a success response with code 200.
    """
    return _my_response(code=200, message=message, **kwargs)


def fail(message='error', **kwargs):
    """
    Returns an error response with the specified code.
    """
    return _my_response(code=400, message=message, **kwargs)


def error(code=400, message='error', **kwargs):
    """
    Returns an error response with the specified code.
    """
    return _my_response(code=code, message=message, **kwargs)


def not_authorized(message='Unauthorized', **kwargs):
    """
    Returns a 401 Unauthorized response.
    """
    return _my_response(code=401, message=message, **kwargs)
