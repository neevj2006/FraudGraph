"""Sample whole-process RSS during a measured command."""

import threading
import time

import psutil


class MemoryMonitor:
    def __enter__(self):
        self.stop = threading.Event()
        self.process = psutil.Process()
        self.peak = self.process.memory_info().rss
        self.started = time.perf_counter()
        self.thread = threading.Thread(target=self.sample, daemon=True)
        self.thread.start()
        return self

    def sample(self):
        while not self.stop.wait(0.02):
            self.peak = max(self.peak, self.process.memory_info().rss)

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join()
        self.peak = max(self.peak, self.process.memory_info().rss)
        self.result = {
            "elapsed_seconds": time.perf_counter() - self.started,
            "sampled_peak_rss_bytes": self.peak,
            "method": "Whole-process RSS sampled every 20 ms; excludes OS filesystem cache and may miss shorter peaks",
        }
