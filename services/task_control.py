import threading

class TaskControl:
    def __init__(self):
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()

    def pause(self):
        self.pause_event.clear()

    def resume(self):
        self.pause_event.set()

    def stop(self):
        self.stop_event.set()
        self.pause_event.set()

    def reset(self):
        self.stop_event.clear()
        self.pause_event.set()

    def wait_if_paused(self):
        self.pause_event.wait()
        if self.stop_event.is_set():
            raise InterruptedError("Task đã bị dừng.")

    def check_stop(self):
        if self.stop_event.is_set():
            raise InterruptedError("Task đã bị dừng.")
