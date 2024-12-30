"""
camera_test.py

Function:
This file is used to see the approximate FPS of the camera used. 
This info is needed for the CV calibartion

"""


import cv2
import time

# Open the camera
cap = cv2.VideoCapture(0)  # Use the appropriate camera index

# Check if the camera opened successfully
if not cap.isOpened():
    print("Error: Could not open camera.")
    exit()

# Initialize variables
num_frames = 120  # Number of frames to capture
start_time = time.time()

for i in range(num_frames):
    ret, frame = cap.read()
    if not ret:
        print("Error: Could not read frame.")
        break

# Calculate the time elapsed and FPS
end_time = time.time()
elapsed_time = end_time - start_time
fps = num_frames / elapsed_time

print(f"Approximate FPS: {fps}")

# Release the camera
cap.release()
cv2.destroyAllWindows()