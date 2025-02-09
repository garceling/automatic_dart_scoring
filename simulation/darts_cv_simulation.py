import time
import random
from flask_socketio import SocketIO
from src.simple_dart_data import DartDataManager, DartThrow

class DartDetection:

    def __init__(self, socketio: SocketIO):
        self.cv_running = False
        self.cv_mode = False #Flag so web app knows when to use cv simulated data
        self.socketio = socketio
        self.data_manager = DartDataManager() #Initializes DartDataManager, the data structure used to interface the cv with the web app
        self.cameras = None
        self.current_user_id = None #used to pass user ID so app will update properly

    def generate_random_score(self):

        multiplier = 1
        position = (0,0) #Fixed position for cv sim testing purposes, real cv will record actual dart position and send it to the web app, so it can be displayed on a little dart display beside the score

        dartboard_numbers = list(range(1, 21)) + [25] #25 is bullseye
        single_score = random.choice(dartboard_numbers)

        if single_score == 25: #no triple for bullseye
            multiplier = random.choice([1, 2]) 
            return (single_score, multiplier, position)
     
        multiplier = random.choices([1, 2, 3], weights=[60, 20, 20])[0]
    

        return (single_score, multiplier, position)

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

        data in the form: (single_score, multiplier, position)

        TODO: return data in the form of x,y coordinates, the app will have a picture of the dartboard
        and plot + calculte the score

        """
        print("DartDetection: CV loop started")  # Debug print

        while self.cv_running:
            if self.cv_mode and self.current_user_id:
                print("DartDetection: Generating throw in CV loop")  # Debug print
                time.sleep(5)  # Simulate deteciton time
                score, multiplier, position = self.generate_random_score()
                print(f"DartDetection: Generated throw - score: {score}, multiplier: {multiplier}, position: {position}")  # Debug print
                self.data_manager.record_throw(position = position, score = score, multiplier = multiplier)
                self.socketio.emit('cv_dart_detected', {'score': score, 'multiplier': multiplier, 'position': position, 'user_id': self.current_user_id})


    def start(self):
        if not self.cv_running:
            self.cv_running = True
            self.socketio.start_background_task(self.cv_loop) #run dart detection

    def stop(self):
        self.cv_running = False #stop the dart deteciton

    def toggle_cv_mode(self, enable: bool, user_id: str = None):
        """Toggle CV mode on/off"""
        print(f"DartDetection: Toggling CV mode to {'enabled' if enable else 'disabled'}")  # Debug print
        self.cv_mode = enable
        self.current_user_id = user_id #store the user id
        mode_status = "enabled" if enable else "disabled"
        print(f"DartDetection: Emitting cv_mode_status: {mode_status}")  # Debug print
        self.socketio.emit('cv_mode_status', {'status': mode_status})
        
    def get_current_throw(self):
        """Get the most recent throw from the data manager"""
        return self.data_manager.get_current_throw()