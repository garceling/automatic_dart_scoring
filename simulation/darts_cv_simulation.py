# darts_cv_simulation.py

import random
import time

class DartDetection:
    def __init__(self):
        self.cv_running = False

    def generate_random_score(self):
        """Generate a random dart score"""
        multiplier = 1
        position = (0, 0)  # Fixed position for cv sim testing purposes

        dartboard_numbers = list(range(1, 21)) + [25]  # 25 is bullseye
        single_score = random.choice(dartboard_numbers)

        if single_score == 25:  # no triple for bullseye
            multiplier = random.choice([1, 2])
        else:
            multiplier = random.choices([1, 2, 3], weights=[60, 20, 20])[0]

        
        print(f"single_score = {single_score}, multiplier = {multiplier}, position = {position}")
        return (single_score, multiplier, position)

    def initialize(self):
        """Simulate initialization time"""
        time.sleep(2)
        print("Dart detection initialized")

    def start(self):
        """Start the simulation"""
        self.cv_running = True

    def stop(self):
        """Stop the simulation"""
        self.cv_running = False

    def get_next_throw(self):
        """Get the next throw if running"""
        if not self.cv_running:
            return None
            
        time.sleep(5)  # Simulate detection time
        return self.generate_random_score()