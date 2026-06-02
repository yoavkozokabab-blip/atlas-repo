from sqlalchemy import create_engine

engine = create_engine("postgresql://localhost/app")

def get_session():
    return engine.connect()
