def tenumerate(iterable, start=0, total=None, tqdm_class=None):
    tqdm_class = tqdm_class or list
    return enumerate(tqdm_class(iterable), start)
