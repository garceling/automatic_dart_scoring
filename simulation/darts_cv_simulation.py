import time
import random
from flask_socketio import SocketIO

class DartDetection:

    def __init__(self, socketio: SocketIO):
        self.cv_running = False
        self.socketio = socketio
        self.cameras = None

    def generate_random_score(self):

        is_double = False
        is_triple = False

        dartboard_numbers = list(range(1, 21)) + [25] #25 is bullseye

        single_score = random.choice(dartboard_numbers)

        if single_score == 25: #no tirple for buleeseye
            is_double = random.choice([True, False]) 
            return (single_score, is_double, False)
     
        multiplier = random.choices(["single", "double", "triple"], weights=[60, 20, 20])[0]
    
        if multiplier == "double":
            is_double = True
        elif multiplier == "triple":
            is_triple = True

        return (single_score, is_double, is_triple)

    def initialize(self):
        """
        This is where the cameras would be open and any other intilization will be done before the
        dart detection

        self.camera = cv2.camera_open()

        """

        time.sleep(2)
        self.socketio.emit('cvinit_status', {'cvInit': 'Done Init'})
        


    def cv_loop(self):
        """
        continuously detects darts and sends scores while running.

        data in the form: (single_score, is_double, is_triple)

        TODO: return data in the form of x,y coordinates, the app will have a picture of the dartboard
        and plot + calculte the score

        """

        while self.cv_running:
            time.sleep(5)  # Simulate deteciton time
            score, is_double, is_triple = self.generate_random_score()
            self.socketio.emit('dart_detected', {'score': score, 'is_double': is_double, 'is_triple': is_triple})


    def start(self):
        if not self.cv_running:
            self.cv_running = True
            self.socketio.start_background_task(self.cv_loop) #run dart detection

    def stop(self):
        self.cv_running = False #stop the dart deteciton
   