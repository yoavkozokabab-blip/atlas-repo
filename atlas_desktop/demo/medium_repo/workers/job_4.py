from services.notify import ping
from services.billing import charge

def run_job_4():
    return ping(), charge('user4')
