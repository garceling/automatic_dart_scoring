from flask import Flask, render_template, url_for
from flask_socketio import SocketIO, emit
from src.calibrate import Calibration_App
import cv2
import numpy as np
import yaml
import os
import time

app = Flask(__name__)
socketio = SocketIO(app)

calibration = Calibration_App()


video_capture = None
camera_index = None

@app.route('/')
def index():
    return render_template('calibration.html', camera_ids=calibration.constants['CAMERA_ID'])

#selects camera + saves image for calibratoin in static folder
@socketio.on('select_camera')
def handle_select_camera(data):
    global video_capture
    global camera_index
    camera_index = data.get('camera_index')
    if camera_index is None:
        emit('error', {'message': 'Camera index not provided'})
        return

    print(f"Selecting camera: {camera_index}")

    if video_capture:
        video_capture.release()

    video_capture = cv2.VideoCapture(camera_index)

    if not video_capture.isOpened():
        emit('error', {'message': f'Unable to access camera {camera_index}'})
    else:
        emit('success', {'message': f'Camera {camera_index} selected successfully'})
        #check if frame read is sucessful
        success, frame = video_capture.read()

        if success:

            image_path = os.path.join('static','snapshot.jpg')
            saved = cv2.imwrite(image_path, frame)

            if saved:
                emit('image_captured', {'image_url': f'static/snapshot.jpg?{int(time.time())}'})
            else:
                emit('error', {'message': 'Failed to save calibration image'})
        else:
            emit('error', {'message': 'Failed to take calibration image'})

#allows user to submit 4 points for calibartion
@socketio.on('submit_points')
def handle_submit_points(data):

    points = data.get('points')
    if not points or len(points) != 4:
        emit('error', {'message': 'You must select exactly 4 points!'})
        return

    # Convert points to NumPy array for processing
    selected_points = np.float32([[p['x'], p['y']] for p in points])
    #print(f"Received points: {selected_points}")

    calibration.save_perspective_matrix(camera_index,selected_points)

    emit('points_saved', {'message': f'Persective matrix is sucessfully generated for camera{camera_index}!'})


if __name__ == '__main__':
    socketio.run(app, host='192.168.40.187', port=5000, debug=False)
