def request_id_middleware(environ, start_response):
    request_id = environ.get("HTTP_X_REQUEST_ID", "local")
    return start_response("200 OK", [("X-Request-ID", request_id)])
