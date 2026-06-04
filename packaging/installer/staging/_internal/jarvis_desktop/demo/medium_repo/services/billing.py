from services.auth import authenticate

def charge(user: str) -> str:
    return authenticate(user)
