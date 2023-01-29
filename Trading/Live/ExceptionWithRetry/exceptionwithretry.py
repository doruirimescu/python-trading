import time
from typing import Callable, Any
import functools

class ExceptionWithRetry:
    """Retries calling the function for n_retry times, with time_sleep in between unsuccessful attempts.
       Does not throw any error if the last retry fails.
    """
    def __init__(self, method, n_retry = 5, time_sleep = 0.5):
        self._method = method
        self._retries = 0
        self._max_retries = n_retry
        self._time_sleep = time_sleep

    def run(self, args):
        if self._retries < self._max_retries:
            self._retries = self._retries + 1
            try:
                return self._method(*args)
            except Exception as e:
                print(e)
                time.sleep(self._time_sleep)
                return self.run(args)


def exception_with_retry(n_retry: int,  sleep_time_s: float):
    """Use this decorator to retry calling your function n_retry times, with sleep_time_s in between unsuccessful calls.
    Will finally throw the original error if the last retry fails.

    Args:
        n_retry (int): number of retries
        sleep_time_s (float): time to sleep between unsuccessful retries, in seconds

    Returns:
        Callable[..., Any]: decorated function
    """
    retries = 0
    def dec(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            nonlocal retries
            try:
                retries += 1
                return func(*args, **kwargs)
            except Exception as e:
                if retries < n_retry:
                    print(e)
                    time.sleep(sleep_time_s)
                    return wrapper(*args, **kwargs)
                else:
                    raise e

        return wrapper
    return dec
