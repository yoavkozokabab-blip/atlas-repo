from services.notify import ping
from services.billing import charge

def run_job_1():
    return ping(), charge('user1')
