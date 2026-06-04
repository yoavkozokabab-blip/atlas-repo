from services.notify import ping
from services.billing import charge

def run_job_7():
    return ping(), charge('user7')
