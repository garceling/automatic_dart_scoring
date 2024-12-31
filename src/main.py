import cv2
import os 
import sys
import argparse
from calibrate import Calibration
from refactor_darts import DartBoard


def start_loop():
    dartboard = DartBoard(cam_R, cam_L, cam_C)
    dartboard.run_loop()

def main():

    #intilize command-line args
    parser = argparse.ArgumentParser(description="Automatic Dart Scoring")
    parser.add_argument("-c", "--calibration", action="store_true", help="Need calibration")
    args = parser.parse_args()
    
    if args.calibration:
        calibration = Calibration()
        #generate the persepctive matrix
        calibration.calibrate()
    #TODO: CHECK/ADD a calibration for to minmize the latency btwn the camera + leds. Adjust timing parameters?
    cam_R = cv2.VideoCapture(0)
    cam_L = cv2.VideoCapture(2)
    cam_C = cv2.VideoCapture(4)

    if not cam_R.isOpened() or not cam_L.isOpened() or not cam_C.isOpened():
        print("Failed to open one or more cameras.")
        sys.exit()
    else:
        start_loop()

if __name__ == "__main__":
    main()