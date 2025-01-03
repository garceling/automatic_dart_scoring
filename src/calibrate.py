import tkinter as tk
from tkinter import messagebox
import cv2
import numpy as np
import math
import time
from shapely.geometry import Point, LineString, Polygon
from typing import List
import os
import sys
import yaml

class Calibration:

    def __init__(self):
        self.constants = self.load_constants()
        self.drawn_points = None
        self.perspective_matrices = []

    def load_constants(self):
        # load yaml file with constagitnt paramters
        with open("config/cv_constants.yaml", "r") as file:
            constants = yaml.safe_load(file)
        return constants

    def select_points_event(self,event, x, y, flags, param):
        frame, selected_points, camera_index = param
        if event == cv2.EVENT_LBUTTONDOWN and len(selected_points) < 4:
            selected_points.append([x, y])
            cv2.circle(frame, (x, y), 5, (0, 255, 0), -1)
            cv2.imshow(f"Camera {camera_index} - Select 4 Points", frame)
            #if len(selected_points) == 4:
            #    cv2.destroyWindow(f"Camera {camera_index} - Select 4 Points")

    def calibrate_camera(self,camera_index):
        cap = cv2.VideoCapture(camera_index)
        ret, frame = cap.read()
        
        if not ret:
            print("Error: Unable to capture frame")
            cap.release()
            return None

        print("4 points are being selected")
        window_name = f"Camera {camera_index} - Select 4 Points"
        cv2.namedWindow(window_name, cv2.WINDOW_GUI_NORMAL)
        selected_points = []

        # Set up the mouse callback function
        cv2.setMouseCallback(window_name, self.select_points_event, (frame, selected_points, camera_index))

        # Display the frame and wait for the user to select points
        while len(selected_points) < 4:
            # Display the current frame
            frame_copy = frame.copy()
            cv2.imshow(window_name, frame_copy)
            
            # Small delay to process events
            if cv2.waitKey(1) & 0xFF == 27:  # Press 'Esc' to exit early if needed
                break

        # Clean up resources
        cv2.destroyAllWindows()
        cap.release()

        # Return selected points if we have 4
        if len(selected_points) >= 4:
            return np.float32(selected_points)
            
    def calibrate(self):
        print("Please select 4 points on each camera feed for calibration.")
        
        center = (self.constants['IMAGE_WIDTH'] // 2, self.constants['IMAGE_HEIGHT'] // 2)
        # Define the drawn_points variable
        self.drawn_points = np.float32([
            [center[0], center[1] - self.constants['DOUBLE_RING_OUTER_RADIUS_PX']],
            [center[0] + self.constants['DOUBLE_RING_OUTER_RADIUS_PX'], center[1]],
            [center[0], center[1] + self.constants['DOUBLE_RING_OUTER_RADIUS_PX']],
            [center[0] - self.constants['DOUBLE_RING_OUTER_RADIUS_PX'], center[1]],
        ])
        
        for camera_index in range(self.constants['NUM_CAMERAS']):
            live_feed_points = self.calibrate_camera(self.constants['CAMERA_ID'][camera_index])
            if live_feed_points is not None:
                M = cv2.getPerspectiveTransform(self.drawn_points, live_feed_points)
                self.perspective_matrices.append(M)
                np.savez(f'perspective_matrix_camera_{camera_index}.npz', matrix=M)
            else:
                print(f"Calibration Error: Failed to calibrate camera {camera_index}")
                return

        print("Calibration completed successfully.")

