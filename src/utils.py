import os
import sys
import cv2
import yaml
from kalman_filter import KalmanFilter

global constants
global perspective_matrices = []

with open("config/constants.yaml", "r") as file:
    constants = yaml.safe_load(file)

def load_perspective_matrices():
    #perspective_matrices = []
    for camera_index in range(constants['NUM_CAMERAS']):
        try:
            data = np.load(f'perspective_matrix_camera_{camera_index}.npz')
            matrix = data['matrix']
            perspective_matrices.append(matrix)
        except FileNotFoundError:
            print(f"Perspective matrix file not found for camera {camera_index}. Please calibrate the cameras first.")
            exit(1)
    return perspective_matrices

def generate_kalman_filters():
    kalman_filter_R = KalmanFilter(constants['DT'], constants['U_X'], constants['U_Y'], constants['STD_ACC'], constants['X_STD_MEAS'], constants['Y_STD_MEAS'])
    kalman_filter_L = KalmanFilter(constants['DT'], constants['U_X'], constants['U_Y'], constants['STD_ACC'], constants['X_STD_MEAS'], constants['Y_STD_MEAS'])
    kalman_filter_C = KalmanFilter(constants['DT'], constants['U_X'], constants['U_Y'], constants['STD_ACC'], constants['X_STD_MEAS'], constants['Y_STD_MEAS'])
    return kalman_filter_R, kalman_filter_L, kalman_filter_C

##################################### Camera/Image Processing Helper Functions #################################3

""" These functions are also used to help detect the precesense of a dart """

def cam2gray(cam):
    success, image = cam.read()
    img_g = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    return success, img_g

def diff2blur(cam, t):
    _, t_plus = cam2gray(cam)
    dimg = cv2.absdiff(t, t_plus)
    kernel = np.ones((5, 5), np.float32) / 25
    blur = cv2.filter2D(dimg, -1, kernel)
    return t_plus, blur

def getCorners(img_in):
    edges = cv2.goodFeaturesToTrack(img_in, 640, 0.0008, 1, mask=None, blockSize=3, useHarrisDetector=1, k=0.06)
    corners = np.intp(edges)
    return corners

def filterCorners(corners):
    mean_corners = np.mean(corners, axis=0)
    corners_new = np.array([i for i in corners if abs(mean_corners[0][0] - i[0][0]) <= 180 and abs(mean_corners[0][1] - i[0][1]) <= 120])
    return corners_new

def filterCornersLine(corners, rows, cols):
    [vx, vy, x, y] = cv2.fitLine(corners, cv2.DIST_HUBER, 0, 0.1, 0.1)
    lefty = int((-x[0] * vy[0] / vx[0]) + y[0])
    righty = int(((cols - x[0]) * vy[0] / vx[0]) + y[0])
    corners_final = np.array([i for i in corners if abs((righty - lefty) * i[0][0] - (cols - 1) * i[0][1] + cols * lefty - righty) / np.sqrt((righty - lefty)**2 + (cols - 1)**2) <= 40])
    return corners_final

def get_threshold(cam, t):
    success, t_plus = cam2gray(cam)
    dimg = cv2.absdiff(t, t_plus)
    blur = cv2.GaussianBlur(dimg, (5, 5), 0)
    blur = cv2.bilateralFilter(blur, 9, 75, 75)
    _, thresh = cv2.threshold(blur, 60, 255, 0)
    return thresh

#################### Calculte the Score Helper Functions ###################################################

def get_score(locationofdart_R,locationofdart_L,locationofdart_C):
    camera_scores = [None] * constants['NUM_CAMERAS']  # Initialize camera_scores list
    for camera_index, locationofdart in enumerate([locationofdart_R, locationofdart_L, locationofdart_C]):
            if isinstance(locationofdart, tuple) and len(locationofdart) == 2:
                x, y = locationofdart
                score = calculate_score_from_coordinates(x, y, camera_index)
                print(f"Camera {camera_index} - Dart Location: {locationofdart}, Score: {score}")

                # Store the score in the camera_scores list
                camera_scores[camera_index] = score
    return camera_scores


def calculate_score_from_coordinates(x, y, camera_index):
    #fix this my making it a global varible??
    inverse_matrix = cv2.invert(perspective_matrices[camera_index])[1]
    transformed_coords = cv2.perspectiveTransform(np.array([[[x, y]]], dtype=np.float32), inverse_matrix)[0][0]
    transformed_x, transformed_y = transformed_coords

    dx = transformed_x - constants['center'][0]
    dy = transformed_y - constants['center'][0]
    distance_from_center = math.sqrt(dx**2 + dy**2)
    angle = math.atan2(dy, dx)
    score = calculate_score(distance_from_center, angle)
    return score

def calculate_score(distance, angle):
    if angle < 0:
        angle += 2 * np.pi
    sector_scores = [10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5, 20, 1, 18, 4, 13, 6]
    sector_index = int(angle / (2 * np.pi) * 20)
    base_score = sector_scores[sector_index]
    if distance <= constants['BULLSEYE_RADIUS_PX']:
        return 50
    elif distance <= constants['OUTER_BULL_RADIUS_PX']:
        return 25
    elif constants['TRIPLE_RING_INNER_RADIUS_PX'] < distance <= constants['TRIPLE_RING_OUTER_RADIUS_PX']:
        return base_score * 3
    elif constants['DOUBLE_RING_INNER_RADIUS_PX'] < distance <= constants['DOUBLE_RING_OUTER_RADIUS_PX']:
        return base_score * 2
    elif distance <= constants['DOUBLE_RING_OUTER_RADIUS_PX']:
        return base_score
    else:
        return 0

def get_score_coordinates(dart_coordinates, majority_camera_index):
    # Transform the dart coordinates to match the drawn dartboard
    if dart_coordinates is not None:
        x, y = dart_coordinates
        inverse_matrix = cv2.invert(perspective_matrices[majority_camera_index])[1]
        transformed_coords = cv2.perspectiveTransform(np.array([[[x, y]]], dtype=np.float32), inverse_matrix)[0][0]
        dart_coordinates = tuple(map(int, transformed_coords))
        return dart_coordinates
    return None

########################### Dartboard GUI drawer helper functions ###############################################
def draw_segment_text(image, center, start_angle, end_angle, radius, text):
    angle = (start_angle + end_angle) / 2
    text_x = int(center[0] + radius * np.cos(angle))
    text_y = int(center[1] + radius * np.sin(angle))
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.5
    font_thickness = 1
    text_size = cv2.getTextSize(text, font, font_scale, font_thickness)[0]
    text_origin = (text_x - text_size[0] // 2, text_y + text_size[1] // 2)
    cv2.putText(image, text, text_origin, font, font_scale, (0, 255, 0), font_thickness, cv2.LINE_AA)

def draw_point_at_angle(image, center, angle_degrees, radius, color, point_radius):
    angle_radians = np.radians(angle_degrees)
    x = int(center[0] + radius * np.cos(angle_radians))
    y = int(center[1] - radius * np.sin(angle_radians))
    cv2.circle(image, (x, y), point_radius, color, -1)

def draw_dartboard():
    # Create a blank image with white background
    dartboard_image = np.ones((constants['IMAGE_HEIGHT'], constants['IMAGE_WIDTH'], 3), dtype=np.uint8) * 255

    # Draw the bullseye and rings
    cv2.circle(dartboard_image, constants['center'], constants['BULLSEYE_RADIUS_PX'], (0, 0, 0), -1, lineType=cv2.LINE_AA)  # Bullseye
    cv2.circle(dartboard_image, constants['center'], constants['OUTER_BULL_RADIUS_PX'], (255, 0, 0), 2, lineType=cv2.LINE_AA)  # Outer bull
    cv2.circle(dartboard_image, constants['center'], constants['TRIPLE_RING_INNER_RADIUS_PX'], (0, 255, 0), 2, lineType=cv2.LINE_AA)  # Inner triple
    cv2.circle(dartboard_image, constants['center'], constants['TRIPLE_RING_OUTER_RADIUS_PX'], (0, 255, 0), 2, lineType=cv2.LINE_AA)  # Outer triple
    cv2.circle(dartboard_image, constants['center'], constants['DOUBLE_RING_INNER_RADIUS_PX'], (0, 0, 255), 2, lineType=cv2.LINE_AA)  # Inner double
    cv2.circle(dartboard_image, constants['center'], constants['DOUBLE_RING_OUTER_RADIUS_PX'], (0, 0, 255), 2, lineType=cv2.LINE_AA)  # Outer double

    # Draw the sector lines
    for angle in np.linspace(0, 2 * np.pi, 21)[:-1]:  # 20 sectors
        start_x = int(constants['center'][0] + np.cos(angle) * constants['DOUBLE_RING_OUTER_RADIUS_PX'])
        start_y = int(constants['center'][1] + np.sin(angle) * constants['DOUBLE_RING_OUTER_RADIUS_PX'])
        end_x = int(constants['center'][0] + np.cos(angle) * constants['OUTER_BULL_RADIUS_PX'])
        end_y = int(constants['center'][1] + np.sin(angle) * constants['OUTER_BULL_RADIUS_PX'])
        cv2.line(dartboard_image, (start_x, start_y), (end_x, end_y), (0, 0, 0), 1, lineType=cv2.LINE_AA)

    text_radius_px = int((constants['TRIPLE_RING_OUTER_RADIUS_PX'] + constants['DOUBLE_RING_INNER_RADIUS_PX']) / 2)

    sector_scores = [10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5, 20, 1, 18, 4, 13, 6]
    for i, score in enumerate(sector_scores):
        start_angle = (i * 360 / 20 - 0) * np.pi / 180
        end_angle = ((i + 1) * 360 / 20 - 0) * np.pi / 180
        draw_segment_text(dartboard_image, constants['center'], start_angle, end_angle, text_radius_px, str(score))

    sector_intersections = {
        '20_1': 0,
        '6_10': 90,
        '19_3': 180,
        '11_14': 270,
    }

    for angle in sector_intersections.values():
        draw_point_at_angle(dartboard_image, constants['center'], angle, constants['DOUBLE_RING_OUTER_RADIUS_PX'], (255, 0, 0), 5)
