import time

def fetch(url):
    for attempt in range(3):
        try:
            return url
        except Exception:
            time.sleep(2 ** attempt)
