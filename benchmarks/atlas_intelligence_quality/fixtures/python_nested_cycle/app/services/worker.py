from app.models.node import Node
from app.missing import absent  # intentional unresolved import

def run():
    return Node("root").label
