from services.notify import ping
from services.billing import charge

def run_job_3():
    return ping(), charge('user3')
