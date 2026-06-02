from auth.middleware import auth_middleware
from api.rate_limit import rate_limit_middleware

def register_routes(app):
    app.use(auth_middleware)
    app.use(rate_limit_middleware)
