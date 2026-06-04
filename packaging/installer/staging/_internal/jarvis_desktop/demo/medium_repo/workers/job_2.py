from services.notify import ping
from services.billing import charge

def run_job_2():
    return ping(), charge('user2')
