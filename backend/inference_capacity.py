"""Limit active and waiting CPU voice requests; overload fails promptly."""
from contextlib import contextmanager
from threading import BoundedSemaphore,Lock
from backend.errors import ValidationError

class InferenceCapacity:
    def __init__(self,maximum=3,timeout=10):
        self.slots=BoundedSemaphore(maximum)
        self.lock=Lock()
        self.timeout=timeout

    @contextmanager
    def acquire(self):
        if not self.slots.acquire(blocking=False):
            raise ValidationError('The voice station is busy. Wait a moment and retry your recording.')
        locked=False
        try:
            locked=self.lock.acquire(timeout=self.timeout)
            if not locked:
                raise ValidationError('The voice station is busy. Wait a moment and retry your recording.')
            yield
        finally:
            if locked: self.lock.release()
            self.slots.release()
