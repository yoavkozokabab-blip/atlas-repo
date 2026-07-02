from app.auth import AuthStore

def test_login():
    assert AuthStore().login('x')
