from concurrent.futures import ProcessPoolExecutor


def reformat_many(worker_count):
    if worker_count > 61:
        worker_count = 61
    try:
        executor = ProcessPoolExecutor(max_workers=worker_count)
    except OSError:
        executor = None
    try:
        return executor
    finally:
        if executor is not None:
            executor.shutdown()


def schedule_formatting(executor):
    if executor is None:
        return "mono"
    return "pool"
