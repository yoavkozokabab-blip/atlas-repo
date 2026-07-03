from shared.config import APP_NAME

def log(msg: str) -> str:
    return f'{APP_NAME}:{msg}'
