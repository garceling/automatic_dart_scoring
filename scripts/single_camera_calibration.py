"""
single_camera_calibration.py

Based on: https://temugeb.github.io/opencv/python/2021/02/02/stereo-camera-calibration-and-triangulation.html

Function:
This file is used to find the intrinsic paramters of the camera used. This info is not "necceraily" needed for the calibration 
of the dartboard. Since the cameras will have a fixed setup and the dartboard itself is treated like a 2D plane.

To use this file, you need to print out a checkboard pattern and calibraite the camera with that. Note: the RMSE value of the cameras we are using
is fairly poor compared to the LOGITECH usb camera. That should not interfer with the results since the cameras will always be placed close to the dartboard

Run this file in the project root directory
"""
import cv2 as cv
import glob
import numpy as np
import yaml
import os
#This will contain the calibration settings from the calibration_settings.yaml file
calibration_settings = {}

#Open and load the calibration_settings.yaml file
def parse_calibration_settings_file(filename):
    
    global calibration_settings

    if not os.path.exists(filename):
        print('File does not exist:', filename)
        quit()
    
    print('Using for calibration settings: ', filename)

    with open(filename) as f:
        calibration_settings = yaml.safe_load(f)

    #rudimentray check to make sure correct file was loaded
    if 'camera0' not in calibration_settings.keys():
        print('camera0 key was not found in the settings file. Check if correct calibration_settings.yaml file was passed')
        quit()
        
def save_frames_single_camera(camera_name):
    #create frames directory
    if not os.path.exists('frames'):
        os.mkdir('frames')

    #get settings
    camera_device_id = calibration_settings[camera_name]
    width = calibration_settings['frame_width']
    height = calibration_settings['frame_height']
    number_to_save = calibration_settings['mono_calibration_frames']
    view_resize = calibration_settings['view_resize']
    cooldown_time = calibration_settings['cooldown']

    #open video stream and change resolution.
    #Note: if unsupported resolution is used, this does NOT raise an error.
    cap = cv.VideoCapture(camera_device_id)
    cap.set(3, width)
    cap.set(4, height)
    
    cooldown = cooldown_time
    start = False
    saved_count = 0

    while True:
    
        ret, frame = cap.read()
        if ret == False:
            #if no video data is received, can't calibrate the camera, so exit.
            print("No video data received from camera. Exiting...")
            quit()

        frame_small = cv.resize(frame, None, fx = 1/view_resize, fy=1/view_resize)

        if not start:
            cv.putText(frame_small, "Press SPACEBAR to start collection frames", (50,50), cv.FONT_HERSHEY_COMPLEX, 1, (0,0,255), 1)
        
        if start:
            cooldown -= 1
            cv.putText(frame_small, "Cooldown: " + str(cooldown), (50,50), cv.FONT_HERSHEY_COMPLEX, 1, (0,255,0), 1)
            cv.putText(frame_small, "Num frames: " + str(saved_count), (50,100), cv.FONT_HERSHEY_COMPLEX, 1, (0,255,0), 1)
            
            #save the frame when cooldown reaches 0.
            if cooldown <= 0:
                savename = os.path.join('frames', camera_name + '_' + str(saved_count) + '.png')
                cv.imwrite(savename, frame)
                saved_count += 1
                cooldown = cooldown_time

        cv.imshow('frame_small', frame_small)
        k = cv.waitKey(1)
        
        if k == 27:
            #if ESC is pressed at any time, the program will exit.
            quit()

        if k == 32:
            #Press spacebar to start data collection
            start = True

        #break out of the loop when enough number of frames have been saved
        if saved_count == number_to_save: break

    cv.destroyAllWindows()

#this is instrinic calibration only
def calibrate_camera_for_intrinsic_parameters(images_folder):
    images_names = sorted(glob.glob(images_folder))
    images = []
    for imname in images_names:
        im = cv.imread(imname, 1)
        images.append(im)
 
    #criteria used by checkerboard pattern detector.
    #Change this if the code can't find the checkerboard
    criteria = (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER, 30, 0.001)
 
    rows = calibration_settings['checkerboard_rows'] #number of checkerboard rows.
    columns = calibration_settings['checkerboard_columns'] #number of checkerboard columns.
    world_scaling = calibration_settings['checkerboard_box_size_scale'] #this will change to user defined length scale
 
    #coordinates of squares in the checkerboard world space
    objp = np.zeros((rows*columns,3), np.float32)
    objp[:,:2] = np.mgrid[0:rows,0:columns].T.reshape(-1,2)
    objp = world_scaling* objp
 
    #frame dimensions. Frames should be the same size.
    width = images[0].shape[1]
    height = images[0].shape[0]
 
    #Pixel coordinates of checkerboards
    imgpoints = [] # 2d points in image plane.
 
    #coordinates of the checkerboard in checkerboard world space.
    objpoints = [] # 3d point in real world space
 
 
    for frame in images:
        gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
 
        #find the checkerboard
        ret, corners = cv.findChessboardCorners(gray, (rows, columns), None)
 
        if ret == True:
 
            #Convolution size used to improve corner detection. Don't make this too large.
            conv_size = (11, 11)
 
            #opencv can attempt to improve the checkerboard coordinates
            corners = cv.cornerSubPix(gray, corners, conv_size, (-1, -1), criteria)
            cv.drawChessboardCorners(frame, (rows,columns), corners, ret)
            cv.imshow('img', frame)
            k = cv.waitKey(500)
 
            objpoints.append(objp)
            imgpoints.append(corners)
 
 
 
    ret, mtx, dist, rvecs, tvecs = cv.calibrateCamera(objpoints, imgpoints, (width, height), None, None)
    print('rmse:', ret)
    print('camera matrix:\n', mtx)
    print('distortion coeffs:', dist)
    print('Rs:\n', rvecs)
    print('Ts:\n', tvecs)
 
    return mtx, dist
if __name__ == '__main__':

    current_path = os.getcwd()
    file_name = "calibration_settings.yaml"
    file_path = os.path.join(current_path, "config", file_name)

    #Open and parse the settings file
    parse_calibration_settings_file(file_path)
    save_frames_single_camera('camera0') #save frames for camera0
    
    images_prefix = os.path.join('frames', 'camera0*')
    cmtx0, dist0 = calibrate_camera_for_intrinsic_parameters(images_prefix) 

  
