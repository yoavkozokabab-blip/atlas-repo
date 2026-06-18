from app.auth import AuthStore

def authenticate(request):
    return AuthStore().login(request.token)
