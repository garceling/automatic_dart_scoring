from dataclasses import dataclass
from typing import Optional, Tuple
import time
import threading

@dataclass
class DartThrow:
    position: Tuple[int,int]
    score: int
    multiplier: int
    bull_flag: bool
    timestamp: float = time.time()

class DartDataManager:
    def __init__(self):
        self.current_throw: Optional[DartThrow] = None
        self._lock = threading.Lock()
        self._last_processed_timestamp = 0

    def record_throw(self, position: Tuple[int, int], score: int, multiplier: int, bull_flag: bool) -> None:
        with self._lock:
            self.current_throw = DartThrow(
                position=position, 
                score=score,
                multiplier=multiplier,
                bull_flag=bull_flag
            )

    def get_current_throw(self) -> Optional[DartThrow]:
        with self._lock:
            if self.current_throw is None:
                return None
                
            # Only return throw if it hasn't been processed
            if self.current_throw.timestamp > self._last_processed_timestamp:
                self._last_processed_timestamp = self.current_throw.timestamp
                return self.current_throw
            return None

    def reset(self) -> None:
        with self._lock:
            self.current_throw = None
            self._last_processed_timestamp = 0
