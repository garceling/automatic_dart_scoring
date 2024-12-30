"""
camera_test.py

Function:
This file is used to see the live-stream output of a camera. It takes in the camera ID
as the input

"""


import cv2
import time
import argparse
parser = argparse.ArgumentParser(description="Open a camera using the specified ID.")
parser.add_argument("camera_id", type=int, help="ID of the camera to open")

# Parse the argument
args = parser.parse_args()
camera_id = args.camera_id
cap = cv2.VideoCapture(camera_id)

if cap.isOpened():
    print("camera is open")


import cv2

# Initialize variables
num = 1

while True:
    # Capture frame-by-frame
    ret, img = cap.read()
    if not ret:
        break  # Exit loop if there's an issue with the camera

    # Display the resulting frame
    cv2.imshow('Frame', img)

    # Check if 'c' key is pressed to capture an image
    if cv2.waitKey(1) & 0xFF == ord('c'):
        # Save the captured image with an incremented filename
        cv2.imwrite(f'/home/pi/images/{num}.jpg', img)
        print(f'Capture {num} Successful!')
        num += 1

    # Stop capturing after three images
    if num == 4:
        break

# Release the capture and close any OpenCV windows
cap.release()
cv2.destroyAllWindows()
