from services.auth import authenticate

def list_routes():
    return authenticate('demo')
