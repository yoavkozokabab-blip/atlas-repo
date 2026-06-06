from services.notify import ping
from services.billing import charge

def run_job_6():
    return ping(), charge('user6')
