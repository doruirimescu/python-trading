import time

class ExceptionWithRetry:
    def __init__(self, method, n_retry = 5, time_sleep = 0.5):
        self._method = method
        self._retries = 0
        self._max_retries = n_retry
        self._time_sleep = time_sleep

    def run(self, args):
        if self._retries < self._max_retries:
            self._retries = self._retries + 1
            try:
                self._method(*args)
            except Exception as e:
                print(e)
                time.sleep(self._time_sleep)
                self.run(args)
