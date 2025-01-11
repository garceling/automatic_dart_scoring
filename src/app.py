from flask import Flask, render_template, Response, request, jsonify
import cv2
import numpy as np
import yaml

app = Flask(__name__)

class Calibration:
    def __init__(self):
        self.constants = self.load_constants()

    def load_constants(self):
        with open("config/cv_constants.yaml", "r") as file:
            constants = yaml.safe_load(file)
        return constants

    def save_perspective_matrix(self, camera_index, points):
        center = (self.constants['IMAGE_WIDTH'] // 2, self.constants['IMAGE_HEIGHT'] // 2)
        drawn_points = np.float32([
            [center[0], center[1] - self.constants['DOUBLE_RING_OUTER_RADIUS_PX']],
            [center[0] + self.constants['DOUBLE_RING_OUTER_RADIUS_PX'], center[1]],
            [center[0], center[1] + self.constants['DOUBLE_RING_OUTER_RADIUS_PX']],
            [center[0] - self.constants['DOUBLE_RING_OUTER_RADIUS_PX'], center[1]],
        ])
        live_feed_points = np.float32(points)
        M = cv2.getPerspectiveTransform(drawn_points, live_feed_points)
        np.savez(f'perspective_matrix_camera_{camera_index}.npz', matrix=M)

calibration = Calibration()

# OpenCV video capture object
video_capture = None

@app.route('/')
def index():
    return render_template('../index.html', camera_ids=calibration.constants['CAMERA_ID'])

@app.route('/select_camera', methods=['POST'])
def select_camera():
    global video_capture
    data = request.json
    camera_index = data['camera_index']

    if video_capture:
        video_capture.release()

    video_capture = cv2.VideoCapture(camera_index)

    if not video_capture.isOpened():
        return jsonify({'error': f'Unable to access camera {camera_index}'}), 400

    return jsonify({'message': f'Camera {camera_index} selected successfully.'}), 200

def generate_frames():
    global video_capture
    while True:
        if video_capture:
            success, frame = video_capture.read()
            if not success:
                break
            _, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/select_points', methods=['POST'])
def select_points():
    data = request.json
    points = data['points']
    camera_index = data['camera_index']
    if len(points) == 4:
        calibration.save_perspective_matrix(camera_index, points)
        return jsonify({'message': f'Camera {camera_index} calibrated successfully.'}), 200
    return jsonify({'error': 'Four points are required.'}), 400

if __name__ == '__main__':
    app.run(host='192.168.40.187', port=5000, debug=False)

