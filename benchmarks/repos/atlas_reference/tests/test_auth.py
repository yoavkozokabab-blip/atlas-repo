def test_auth():
    from auth.middleware import authenticate_jwt
    assert authenticate_jwt("token")
