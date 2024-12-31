"""
darts.py

Function:
This file is where the integreation of the 3 modules will interact. I "meat and potateos" of each module should be in their own 
sepeate class/file. Within the init of this class, the module constructor should be called

Within run_loop, the app/led interation should be added. I do not want to clutter main.py with code ( want main to be more high level ctrl)

"""

import time
import os
import sys
import yaml
import cv2

class DartBoard:

    #whatever is in the constructor is what is shared between the app/led/camera
    def __init__(self,cam_R,cam_L,cam_C):
        self.score = None 
        self.game_mode = "501" #make this the default
        self.single_color = None
        self.double_color = None
        self.triple_color = None
        self.success = False
        self.db_cv = DartBoard_CV(cam_R,cam_L,cam_C) #call the constructor
        #TODO: call the LED constrcutor


    #TODO: Potentially have different run_loops for each game mode
    def run_loop(self):

        self.success = self.db_cv.cv_intilization()

        while self.success:

            self.db_cv.check_camera_working()
            if self.db_cv.get_success_value():
                break

            time.sleep(0.1)

            found_movement = self.db_cv.check_thresholds()
            #detect movement? could be dart?
            if found_movement:
                time.sleep(0.2)
                #confirmed to be a dart
                if self.dart_detection():
                    try:
                        self.calculate_score()
                        #TODO: add the turn on LED light here
                        #TODO: send the score update to the user app
                    except Exception as e:
                        print(f"Something went wrong in finding the dart's location: {str(e)}")
                        continue
                    # Update the reference frames after a dart has been detected
                    self.success = self.update_reference_frame()
                else:
                    #move to the next iteration
                    continue
            else:
                self.takeout_procedure()
            
            self.display_score()
            #TODO: add option to correct the score on the app
        
        self.destroy()