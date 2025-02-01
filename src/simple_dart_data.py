from dataclasses import dataclass
from typing import Optional, Tuple
import time

@dataclass
class DartThrow:
    #data structure for processing dart scores between grace's smart vision and my web app
    position: Tuple[int,int] # (x,y) coordinates on dartboard for dartboard display in app (benji will design)
    score: int
    multiplier: int
    timestamp: float = time.time()

class DartDataManager:
    def __init__(self):
        self.current_throw: Optional[DartThrow] = None

    def record_throw(self, position: Tuple[int, int], score: int, multiplier: int) -> None:
        #records a new dart throw
        self.current_throw = DartThrow(
            position=position, 
            score=score,
            multiplier=multiplier
        )

    def get_current_throw(self) -> Optional[DartThrow]:
        #returns the most recent dart throw"
        return self.current_throw
