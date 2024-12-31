"""
refactor_darts.py

Function:
This file is the refactor version of darts.py. The main purpose of this file is to be able to throw 
a single dart and the score be updated and sent to the the "app". Ideally, the system should also be able to recognize that
the dart is being removed, eventually in the main.py, the leds functionality should be added

"""
import yaml
import os
import sys
import time
import cv2
import numpy
from kalman_filter import KalmanFilter
from utils import *

class DartBoard:

    def __init__(self,cam_R, cam_L, cam_C):
        self.cam_R = cam_R
        self.cam_L = cam_L
        self.cam_C = cam_C
        self.camera_scores = [None] * NUM_CAMERAS  # Initialize camera_scores list
        self.majority_score = None
        self.dart_coordinates = None
        self.prev_tip_point_R = None
        self.prev_tip_point_L = None
        self.prev_tip_point_C = None
        self.success = False
        self.t_R = None
        self.t_L = None
        self.t_C = None
        self.thresh_C = None
        self.thresh_L = None
        self.thresh_R = None
        self.dartboard_image = None
        self.perspective_matrices = []
        self.center = calculate_center()
        self.constants = load_constants()
        self.score_images = None

    def load_constants(self):
        # load yaml file with constant paramters
        with open("config/constants.yaml", "r") as file:
            constants = yaml.safe_load(file)
        return constants

    def calculate_center(self):
        center = (constants['IMAGE_WIDTH'] // 2, constants['IMAGE_HEIGHT'] // 2)
        return center

    def initialize_test_cameras(self):
        # Read first image twice to start loop
        self.update_reference_frame()
        time.sleep(0.1)
        self.update_reference_frame()

    def check_thresholds(self):
        ''' 
        Counts the number of non-zero pixels in the threshold images. It checks if the nnz is within 
        a range of 1000-7500. This likely indicates a movement ( ie: dart being thrown). There is a upper 
        limit as that could be caused by too much noise/movement
        '''
       self.thresh_R = utils.get_threshold(self.cam_R, self.t_R)
        thresh_L = utils.get_treshold(self.cam_L, self.t_L)
        thresh_C = utils.get_threshold(self.cam_C, self.t_C)

        non_zero_R = cv2.countNonZero(thresh_R)
        non_zero_L = cv2.countNonZero(thresh_L)
        non_zero_C = cv2.countNonZero(thresh_C)

        if ((1000 < non_zero_R < 7500) or 
            (1000 < non_zero_L < 7500) or 
            (1000 < non_zero_C < 7500)):
            return True
        else:
            thresh_C = None
            thresh_L = None
           self.thresh_R = None
            return False

    def corner_detection(blur_R, blur_L, blur_C):
        ''' 
        Applies a diff operation (frame subtraction). followed by a blurring to highlihgt any changes 
        in the frame. It then detects corners (features) in the blurred frame to find the dart
        '''

        corners_R = utils.getCorners(blur_R)
        corners_L = utils.getCorners(blur_L)
        corners_C = utils.getCorners(blur_C)

        if corners_R.size < 40 and corners_L.size < 40 and corners_C.size < 40:
            print("---- Dart Not Detected -----")
            return False, None, None, None
        return True, corners_R, corners_L, corners_C

    def filtered_corner_detection(corners_R, corners_L, corners_C):
        corners_f_R = utils.filterCorners(corners_R)
        corners_f_L = utils.filterCorners(corners_L)
        corners_f_C = utils.filterCorners(corners_C)

        if corners_f_R.size < 30 and corners_f_L.size < 30 and corners_f_C.size < 30:
            print("---- Filtered Dart Not Detected -----")
            return False, None, None, None
        return True, corners_f_R, corners_f_L, corners_f_C

    def dart_detection():
        #applies frame subtraction
        t_plus_R, blur_R = utils.diff2blur(cam_R, t_R)
        t_plus_L, blur_L = utils.diff2blur(cam_L, t_L)
        t_plus_C, blur_C = utils.diff2blur(cam_C, t_C)

        found_corner_detection, corners_R, corners_L, corners_C = corner_detection(blur_R, blur_L, blur_C)
        if not found_corner_detection:
            return False

        found_filter_corner_detection,corners_f_R, corners_f_L, corners_f_C = filtered_corner_detection(corners_R, corners_L, corners_C)

        if not found_filter_corner_detection:
            return False

        rows, cols = blur_R.shape[:2]
        corners_final_R = utils.filterCornersLine(corners_f_R, rows, cols)
        rows, cols = blur_L.shape[:2]
        corners_final_L = utils.filterCornersLine(corners_f_L, rows, cols)
        rows, cols = blur_C.shape[:2]
        corners_final_C = utils.filterCornersLine(corners_f_C, rows, cols)

        #final dart detection
        _,self.thresh_R = cv2.threshold(blur_R, 60, 255, 0)
        _, thresh_L = cv2.threshold(blur_L, 60, 255, 0)
        _, thresh_C = cv2.threshold(blur_C, 60, 255, 0)

        if cv2.countNonZero(thresh_R) > 15000 or cv2.countNonZero(thresh_L) > 15000 or cv2.countNonZero(thresh_C) > 15000:
            return False

        print("Dart detected")
        return True
    
    def takeout_procedure(self):
        if cv2.countNonZero(self.thresh_R) > TAKEOUT_THRESHOLD or cv2.countNonZero(self.thresh_L) > TAKEOUT_THRESHOLD or cv2.countNonZero(self.thresh_C) > TAKEOUT_THRESHOLD:
            #reset variables
            self.prev_tip_point_R = None
            self.prev_tip_point_L = None
            self.prev_tip_point_C = None
            self.majority_score = None
            self.dart_coordinates = None

            # Wait for the specified delay to allow hand removal
            start_time = time.time()
            while time.time() - start_time < TAKEOUT_DELAY:
                success, t_R = cam2gray(cam_R)
                _, t_L = cam2gray(cam_L)
                _, t_C = cam2gray(cam_C)
                time.sleep(0.1)

            print("Takeout procedure completed.")
            

    def update_reference_frame(self):
        self.success, self.t_R = cam2gray(self.cam_R)
        _, self.t_L = cam2gray(self.cam_L)
        _, self.t_C = cam2gray(self.cam_C)

    def get_score(self,locationofdart_R,locationofdart_L,locationofdart_C):
        for camera_index, locationofdart in enumerate([locationofdart_R, locationofdart_L, locationofdart_C]):
                if isinstance(locationofdart, tuple) and len(locationofdart) == 2:
                    x, y = locationofdart
                    score = calculate_score_from_coordinates(x, y, camera_index)
                    print(f"Camera {camera_index} - Dart Location: {locationofdart}, Score: {score}")

                    # Store the score in the camera_scores list
                    camera_scores[camera_index] = score
    
    def calculate_score(self):
        locationofdart_R, prev_tip_point_R = getRealLocation(corners_final_R, "right", prev_tip_point_R, blur_R, kalman_filter_R)
        locationofdart_L, prev_tip_point_L = getRealLocation(corners_final_L, "left", prev_tip_point_L, blur_L, kalman_filter_L)
        locationofdart_C, prev_tip_point_C = getRealLocation(corners_final_C, "center", prev_tip_point_C, blur_C, kalman_filter_C)

        get_score(locationofdart_R, locationofdart_L, locationofdart_C)

        final_score = calculate_majority_score(camera_scores)
        
        if final_score is not None:
            majority_camera_index = camera_scores.index(final_score)
            dart_coordinates = (locationofdart_R, locationofdart_L, locationofdart_C)[majority_camera_index]
            dart_coordinates = plot_score(dart_coordinates, majority_camera_index)
            print(f"Final Score (Majority Rule): {final_score}")
        else:
            print("No majority score found.")
    
    def plot_score(self):
        # Display the scores and dart coordinates on the dartboard image
        dartboard_image_copy = dartboard_image.copy()
        if majority_score is not None:
            cv2.putText(dartboard_image_copy, f"Majority Score: {majority_score}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)
        if dart_coordinates is not None:
            x, y = dart_coordinates
            cv2.circle(dartboard_image_copy, (int(x), int(y)), 5, (0, 0, 255), -1)
        cv2.imshow('Dartboard', dartboard_image_copy)

        key = cv2.waitKey(1) & 0xFF

        # Check for 'q' (quit)
        if key == ord('q'):
            break

    def destroy(self):
        caps = []  # Define the variable "caps" as an empty list
        for cap in caps:
            cap.release()
        cv2.destroyAllWindows()

    def run_loop(self):
        initialize_test_cameras()
        perspective_matrices = utils.load_perspective_matrices()
        # initialize Kalman filters for each camera
        kalman_filter_R, kalman_filter_L, kalman_filter_C = utils.generate_kalman_filters()

        while self.success:
            #attempts to read frame from each camera (check if camera work properly)
            for camera_index, cam in enumerate([self.cam_R, self.cam_L, self.cam_C]):
                ret, frame = cam.read()
                if not ret:
                    break
             time.sleep(0.1)

            found_movement,self.thresh_R, thresh_L, thresh_C = check_thresholds()

            if found_movement:
                time.sleep(0.2)
                if self.dart_detection():
                    try:
                        self.calculate_score()
                        #TODO: add the turn on LED light here
                        
                    except Exception as e:
                        print(f"Something went wrong in finding the dart's location: {str(e)}")
                        continue
                    # Update the reference frames after a dart has been detected
                    self.update_reference_frame()
                else:
                    #move to the next iteration
                    continue
            else:
                self.takeout_procedure()
            
            self.display_score()
        
        self.destroy()