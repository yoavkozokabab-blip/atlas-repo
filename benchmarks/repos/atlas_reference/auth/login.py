from auth.session import create_session

def login(user, password):
    return create_session(user)
