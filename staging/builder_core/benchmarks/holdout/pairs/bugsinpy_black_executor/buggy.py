from concurrent.futures import ProcessPoolExecutor


def reformat_many(worker_count):
    if worker_count > 61:
        worker_count = 61
    executor = ProcessPoolExecutor(max_workers=worker_count)
    try:
        return executor
    finally:
        executor.shutdown()


def schedule_formatting(executor):
    if executor is None:
        return "mono"
    return "pool"
