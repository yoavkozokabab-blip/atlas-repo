from services.notify import ping
from services.billing import charge

def run_job_8():
    return ping(), charge('user8')
