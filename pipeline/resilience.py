import time
import random
import functools
from urllib.error import HTTPError, URLError


def retry_with_backoff(max_retries: int = 3, backoff_factor: float = 2.0, exceptions=(HTTPError, URLError, Exception)):
    """
    Decorator for retrying functions on failure with Exponential Backoff + Jitter.
    Handles HTTP 429 (Rate Limit) by sleeping according to Retry-After or exponential delay.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    retries += 1
                    if retries > max_retries:
                        raise e

                    # Check for HTTP 429 Rate Limit
                    sleep_time = (backoff_factor ** retries) + random.uniform(0.1, 0.5)
                    if isinstance(e, HTTPError):
                        if e.code == 429:
                            retry_after = e.headers.get('Retry-After')
                            if retry_after and retry_after.isdigit():
                                sleep_time = float(retry_after)
                        elif e.code in [500, 502, 503, 504]:
                            pass  # Server error, proceed with backoff
                        elif e.code in [400, 401, 403, 404]:
                            # Client error non-retryable
                            raise e

                    time.sleep(sleep_time)
        return wrapper
    return decorator
