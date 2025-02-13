import cv2 as cv
import numpy as np
import time
from utils import *

class DartDetection:
    def __init__(self):
        self.stream = cv.VideoCapture(2)
        if not self.stream.isOpened():
            raise Exception("Could not open webcam")

        self.stream.set(cv.CAP_PROP_FRAME_WIDTH, 1280)
        self.stream.set(cv.CAP_PROP_FRAME_HEIGHT, 720)

    def detect_darts(self):
        load_perspective_matrices()
        
        # Initialize the KNN background subtractor
        backSub = cv.createBackgroundSubtractorKNN(dist2Threshold=800)
        
        # Initialize tracking variables
        lastFrame = None
        lastFrame_mask = None
        maxArea = 0
        x_bot = 0
        y_bot = 0
        
        # Variables for movement stop detection
        no_movement_frames = 0
        movement_threshold = 4  # Number of frames to wait before confirming no movement
        last_significant_contour = None

        print("Dart Detection Started:")
        print("- Wait a few seconds for the background to stabilize")
        print("- Throw your dart")
        print("- Press 'q' to quit")

        while True:
            ret, frame = self.stream.read()
            if frame is None:
                break

            frame = cv.resize(frame, (800, 800))
            
            # Apply background subtraction
            fgMask = backSub.apply(frame)
            fgMask_th = cv.threshold(fgMask, 120, 255, cv.THRESH_BINARY)[1]

            # Find contours
            contours, _ = cv.findContours(fgMask_th, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)

            # Check for significant movement
            significant_movement = False
            for contour in contours:
                area = cv.contourArea(contour)
                if area > 100:
                    significant_movement = True
                    if area > maxArea:
                        maxArea = area
                        lastFrame = frame.copy()
                        lastFrame_mask = fgMask.copy()
                        last_significant_contour = contour
                        Bottom = tuple(contour[contour[:, :, 1].argmax()][0])
                        x_bot, y_bot = int(Bottom[0]), int(Bottom[1])
                        
                        # Draw on current frame
                        cv.circle(frame, Bottom, 8, (0, 0, 255), -1)
                        cv.drawContours(frame, [contour], -1, (0, 255, 0), 2)

            # Update movement stop detection
            if significant_movement:
                no_movement_frames = 0
            else:
                no_movement_frames += 1

            # Show impact point quickly after movement stops
            if no_movement_frames >= movement_threshold and last_significant_contour is not None:
                if lastFrame is not None:
                    # Draw impact point and info on last frame
                    cv.circle(lastFrame, (x_bot, y_bot), 8, (0, 0, 255), -1)
                    score = calculate_score_from_coordinates(x_bot,y_bot,1)
                    cv.drawContours(lastFrame, [last_significant_contour], -1, (0, 255, 0), 2)
                    text = f"Impact Point: X={x_bot}, Y={y_bot}, score = {score}"
                    cv.putText(lastFrame, text, (50, 50), 
                              cv.FONT_HERSHEY_SIMPLEX, 0.5, 
                              (0, 0, 255), 1, cv.LINE_AA)
                    
                    cv.imshow("Impact Frame", lastFrame)
                    
                    # Reset for next throw
                    maxArea = 0
                    last_significant_contour = None
                    no_movement_frames = 0

            # Show live feed
            cv.imshow('Live Feed', frame)
            cv.imshow("Motion Mask", fgMask_th)

            if cv.waitKey(1) & 0xFF == ord('q'):
                break

        self.stream.release()
        cv.destroyAllWindows()

if __name__ == "__main__":
    try:
        detector = DartDetection()
        detector.detect_darts()
    except Exception as e:
        print(f"An error occurred: {e}")