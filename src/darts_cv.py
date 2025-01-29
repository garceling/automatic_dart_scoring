"""
darts_cv.py

Function:
This file is the refactor version of darts.py from the github repo. The main purpose of this file is that it contains the functions
used for the computer vision to recognize and calculte the score. Ideally, the system should also be able to recognize that
the dart is being removed

"""
import yaml
import os
import sys
import time
import cv2
from kalman_filter import KalmanFilter
from utils import *
import numpy as np
import math
from shapely.geometry import Point, LineString, Polygon
from typing import List
from simple_dart_data import DartDataManager #for getting dart info into web app.

class DartBoard_CV:

    def __init__(self,cam_R, cam_L, cam_C):
        #TODO: clean this up/group em

        self.cam_R = cam_R
        self.cam_L = cam_L
        self.cam_C = cam_C
        self.constants = self.load_constants()
        #self.camera_scores = [None] * self.constants['NUM_CAMERAS']  # Initialize camera_scores list
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
        self.dartboard_image = draw_dartboard()
        self.perspective_matrices = []
        self.score_images = None
        self.kalman_filter_R = None
        self.kalman_filter_L = None
        self.kalman_filter_C = None
        self.corners_final_R = None
        self.corners_final_L = None
        self.corners_final_C = None 
        self.blur_R = None
        self.blur_L = None
        self.blur_C = None
    
    def get_success_value(self):
        return self.success

    def update_reference_frame(self):
        self.success, self.t_R = cam2gray(self.cam_R)
        _, self.t_L = cam2gray(self.cam_L)
        _, self.t_C = cam2gray(self.cam_C)
        return self.success

    def check_camera_working(self):
        for camera_index, cam in enumerate([self.cam_R, self.cam_L, self.cam_C]):
            ret, frame = cam.read()
            if not ret:
                print(f"Error: Camera {camera_index} failed to return a frame.")
                self.success = False  # Exit the while loop
                break  

    def load_constants(self):
        # load yaml file with constant paramters
        with open("config/cv_constants.yaml", "r") as file:
            constants = yaml.safe_load(file)

    def initialize_test_cameras(self):
        # Read first image twice to start loop
        self.update_reference_frame()
        time.sleep(0.1)
        self.update_reference_frame()
    
    def cv_intilization(self):
        self.initialize_test_cameras()
        self.perspective_matrices = load_perspective_matrices()
        # initialize Kalman filters for each camera
        self.kalman_filter_R, self.kalman_filter_L, self.kalman_filter_C = generate_kalman_filters()
        return self.success

    def check_thresholds(self):
        ''' 
        Counts the number of non-zero pixels in the threshold images. It checks if the nnz is within 
        a range of 1000-7500. This likely indicates a movement ( ie: dart being thrown). There is a upper 
        limit as that could be caused by too much noise/movement
        '''
        self.thresh_R = get_threshold(self.cam_R, self.t_R)
        self.thresh_L = get_treshold(self.cam_L, self.t_L)
        self.thresh_C = get_threshold(self.cam_C, self.t_C)

        non_zero_R = cv2.countNonZero(self.thresh_R)
        non_zero_L = cv2.countNonZero(self.thresh_L)
        non_zero_C = cv2.countNonZero(self.thresh_C)

        if ((1000 < non_zero_R < 7500) or 
            (1000 < non_zero_L < 7500) or 
            (1000 < non_zero_C < 7500)):
            return True
        else:
            self.thresh_C = None
            self.thresh_L = None
            self.thresh_R = None
            return False

    def corner_detection(self,blur_R, blur_L, blur_C):
        ''' 
        Applies a diff operation (frame subtraction). followed by a blurring to highlihgt any changes 
        in the frame. It then detects corners (features) in the blurred frame to find the dart
        '''

        corners_R = getCorners(blur_R)
        corners_L = getCorners(blur_L)
        corners_C = getCorners(blur_C)

        if corners_R.size < 40 and corners_L.size < 40 and corners_C.size < 40:
            print("---- Dart Not Detected -----")
            return False, None, None, None
        return True, corners_R, corners_L, corners_C

    def filtered_corner_detection(self,corners_R, corners_L, corners_C):
        corners_f_R = filterCorners(corners_R)
        corners_f_L = filterCorners(corners_L)
        corners_f_C = filterCorners(corners_C)

        if corners_f_R.size < 30 and corners_f_L.size < 30 and corners_f_C.size < 30:
            print("---- Filtered Dart Not Detected -----")
            return False, None, None, None
        return True, corners_f_R, corners_f_L, corners_f_C

    def dart_detection(self):
        #applies frame subtraction
        t_plus_R, self.blur_R = diff2blur(cam_R, t_R)
        t_plus_L, self.blur_L = diff2blur(cam_L, t_L)
        t_plus_C, self.blur_C = diff2blur(cam_C, t_C)

        found_corner_detection, corners_R, corners_L, corners_C = self.corner_detection(blur_R, blur_L, blur_C)
        if not found_corner_detection:
            return False

        found_filter_corner_detection,corners_f_R, corners_f_L, corners_f_C = self.filtered_corner_detection(corners_R, corners_L, corners_C)

        if not found_filter_corner_detection:
            return False

        rows, cols = blur_R.shape[:2]
        self.corners_final_R = filterCornersLine(corners_f_R, rows, cols)
        rows, cols = blur_L.shape[:2]
        self.corners_final_L = filterCornersLine(corners_f_L, rows, cols)
        rows, cols = blur_C.shape[:2]
        self.corners_final_C = filterCornersLine(corners_f_C, rows, cols)

        #final dart detection
        _,self.thresh_R = cv2.threshold(blur_R, 60, 255, 0)
        _, self.thresh_L = cv2.threshold(blur_L, 60, 255, 0)
        _, self.thresh_C = cv2.threshold(blur_C, 60, 255, 0)

        if cv2.countNonZero(self.thresh_R) > 15000 or cv2.countNonZero(self.thresh_L) > 15000 or cv2.countNonZero(self.thresh_C) > 15000:
            return False

        print("Dart detected")
        return True
    
    def getRealLocation(self, mount):
        if mount == "right":
            loc = np.argmax(corners_final, axis=0)
            blur = self.blur_R
            prev_tip_point = self.prev_tip_point_R
            kalman_filter = self.kalman_filter_R
            corners_final = self.corners_final_R
        elif mount == "center":
            loc = np.argmin(corners_final, axis=0)
            blur = self.blur_C
            prev_tip_point = self.prev_tip_point_C
            kalman_filter = self.kalman_filter_C    
            corners_final = self.corners_final_C
        elif mount == "left":
            loc = np.argmin(corners_final, axis=0)
            blur = self.blur_L
            prev_tip_point = self.prev_tip_point_L
            kalman_filter = self.kalman_filter_L 
            corners_final = self.corners_final_L

        locationofdart = corners_final[loc]
        
        # Skeletonize the dart contour
        dart_contour = corners_final.reshape((-1, 1, 2))
        skeleton = cv2.ximgproc.thinning(cv2.drawContours(np.zeros_like(blur), [dart_contour], -1, 255, thickness=cv2.FILLED))
        
        # Detect the dart tip using skeletonization and Kalman filter
        dart_tip = find_dart_tip(skeleton, prev_tip_point, mount)
        
        if dart_tip is not None:
            tip_x, tip_y = dart_tip
            # Draw a circle around the dart tip
            if blur is not None:
                cv2.circle(blur, (tip_x, tip_y), 5, (0, 255, 0), 2)
            
            locationofdart = dart_tip
        
        return locationofdart, dart_tip

    def find_dart_tip(skeleton, prev_tip_point, mount):


        # Find the contour of the skeleton
        contours, _ = cv2.findContours(skeleton, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if len(contours) > 0:
            # Find the contour with the maximum area (assuming it represents the dart)
            dart_contour = max(contours, key=cv2.contourArea)

            # Convert the contour to a Shapely Polygon
            dart_polygon = Polygon(dart_contour.reshape(-1, 2))

            # Find the lowest point of the dart contour
            dart_points = dart_polygon.exterior.coords
            lowest_point = max(dart_points, key=lambda x: x[1])

            # Adjust the tip coordinates by half of the tip's diameter
            tip_radius_px = constants['TIP_RADIUS_MM'] * constants['PIXELS_PER_MM']

            # Determine the adjustment direction based on the camera's perspective
            adjustment_direction = 0  # Adjust towards the dartboard center (negative direction)

            # Calculate the adjusted tip coordinates
            adjusted_tip_x = lowest_point[0] + adjustment_direction * tip_radius_px
            adjusted_tip_y = lowest_point[1]

            if mount == "right":
                # Predict the dart tip position using the Kalman filter
                predicted_tip = self.kalman_filter_R.predict()
                
                # Update the Kalman filter with the observed dart tip position
                self.kalman_filter_R.update(np.array([[adjusted_tip_x], [adjusted_tip_y]]))
            
            elif mount == "center":
                predicted_tip = self.kalman_filter_C.predict()
                self.kalman_filter_R.update(np.array([[adjusted_tip_x], [adjusted_tip_y]]))

            elif mount == "left":
                predicted_tip = self.kalman_filter_L.predict()
                self.kalman_filter_L.update(np.array([[adjusted_tip_x], [adjusted_tip_y]]))

            return int(adjusted_tip_x), int(adjusted_tip_y)
        
        return None
    
    def calculate_majority_score(self):
        score_counts = {}
        for score in self.camera_scores:
            if score is not None:
                score_counts[score] = score_counts.get(score, 0) + 1

        if score_counts:
            return max(score_counts, key=score_counts.get)

        return None
        
    def transform_score(self, majority_camera_index):
        x, y = self.dart_coordinates
        inverse_matrix = cv2.invert(self.perspective_matrices[majority_camera_index])[1]
        transformed_coords = cv2.perspectiveTransform(np.array([[[x, y]]], dtype=np.float32), inverse_matrix)[0][0]
        self.dart_coordinates = tuple(map(int, transformed_coords))


    def get_multiplier_and_bull_flag(self, distance: float) -> Tuple[int, bool]:
        
        #Determines the multiplier and if throw is in bull/bullseye
        #Returns: (multiplier, bull_flag)
        
        if distance <= self.constants['BULLSEYE_RADIUS_PX'] or distance <= self.constants['OUTER_BULL_RADIUS_PX']:
            return 1, True  # Bull or Bullseye: single multiplier and bull flag True
        elif (self.constants['TRIPLE_RING_INNER_RADIUS_PX'] < distance <= 
              self.constants['TRIPLE_RING_OUTER_RADIUS_PX']):
            return 3, False  # Triple
        elif (self.constants['DOUBLE_RING_INNER_RADIUS_PX'] < distance <= 
              self.constants['DOUBLE_RING_OUTER_RADIUS_PX']):
            return 2, False  # Double
        else:
            return 1, False  # Single

    def calculate_score(self): #changed by Lawrence
        locationofdart_R, self.prev_tip_point_R = self.getRealLocation("right")
        locationofdart_L, self.prev_tip_point_L = self.getRealLocation("left")
        locationofdart_C, self.prev_tip_point_C = self.getRealLocation("center")

        self.get_score(locationofdart_R, locationofdart_L, locationofdart_C)

        self.majority_score = calculate_majority_score()
        
        if self.majority_score is not None:
            majority_camera_index = self.camera_scores.index(self.majority_score)
            self.dart_coordinates = (locationofdart_R, locationofdart_L, locationofdart_C)[majority_camera_index]
            self.transform_score(majority_camera_index)

            #additional code for getting multiplier
            x, y = self.dart_coordinates
            dx = x - self.constants['center'][0]
            dy = y - self.constants['center'][1]
            distance_from_center = math.sqrt(dx**2 + dy**2)

            multiplier, bull_flag = self.get_multiplier_and_bull_flag(distance_from_center)
            
            self.data_manager.record_throw(
                position=self.dart_coordinates,
                score=self.majority_score,
                multiplier=multiplier,
                bull_flag=bull_flag
            )           
            
            print(f"Final Score (Majority Rule): {self.majority_score}")
        else:
            print("No majority score found.")


    def takeout_procedure(self):
        if cv2.countNonZero(self.thresh_R) > constants['TAKEOUT_THRESHOLD'] or cv2.countNonZero(self.thresh_L) > constants['TAKEOUT_THRESHOLD'] or cv2.countNonZero(self.thresh_C) > constants['TAKEOUT_THRESHOLD']:
            #reset variables
            self.prev_tip_point_R = None
            self.prev_tip_point_L = None
            self.prev_tip_point_C = None
            self.majority_score = None
            self.dart_coordinates = None

            # Wait for the specified delay to allow hand removal
            start_time = time.time()
            while time.time() - start_time < constants['TAKEOUT_DELAY']:
                self.update_reference_frame()
                time.sleep(0.1)

            print("Takeout procedure completed.")

    def plot_score(self):
        # Display the scores and dart coordinates on the dartboard image
        dartboard_image_copy = self.dartboard_image.copy()
        if self.majority_score is not None:
            cv2.putText(dartboard_image_copy, f"Majority Score: {self.majority_score}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)
        if self.dart_coordinates is not None:
            x, y = self.dart_coordinates
            cv2.circle(dartboard_image_copy, (int(x), int(y)), 5, (0, 0, 255), -1)
        cv2.imshow('Dartboard', dartboard_image_copy)



    def destroy(self):
        caps = []  # Define the variable "caps" as an empty list
        for cap in caps:
            cap.release()
        cv2.destroyAllWindows()

    '''

    def run_loop(self):
        initialize_test_cameras()
        perspective_matrices = load_perspective_matrices()
        # initialize Kalman filters for each camera
        kalman_filter_R, kalman_filter_L, kalman_filter_C = generate_kalman_filters()

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
        '''
