"""
get_camera_info.py

Function:
This file is used to get the frame width and height of the camera used. This info is 
needed during the calibartion of the cameras for the computer vision

"""


import cv2

# Open the camera (0 is usually the default webcam)
cap = cv2.VideoCapture(0)

if cap.isOpened():
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    print(f"Frame width: {frame_width}, Frame height: {frame_height}")

cap.release()