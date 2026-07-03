from services.notify import ping
from services.billing import charge

def run_job_5():
    return ping(), charge('user5')
