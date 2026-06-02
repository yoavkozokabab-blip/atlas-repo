def trace_middleware(request, next_handler):
    return next_handler(request)
