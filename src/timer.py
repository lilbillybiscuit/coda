import time
from src.formatting import Color
ENABLE_TIMING = True  # Global switch for timing measurements


class Timer:
    """Context manager for timing code blocks"""

    def __init__(self, name):
        self.name = name
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, *args):
        if ENABLE_TIMING:
            elapsed_time = time.time() - self.start_time
            Color.colorize("cyan", bold=True, text=f"⏱️ {self.name}: {elapsed_time:.2f} seconds")
