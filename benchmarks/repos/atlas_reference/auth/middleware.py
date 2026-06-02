def authenticate_jwt(token):
    return token is not None

def auth_middleware(request, next_handler):
    authenticate_jwt(request.headers.get("Authorization"))
    return next_handler(request)
