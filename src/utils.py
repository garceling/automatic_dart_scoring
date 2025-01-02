import os
import sys
import cv2
import yaml
from kalman_filter import KalmanFilter

global constants

with open("config/constants.yaml", "r") as file:
    constants = yaml.safe_load(file)

def load_perspective_matrices():
    perspective_matrices = []
    for camera_index in range(constans['NUM_CAMERAS']):
        try:
            data = np.load(f'perspective_matrix_camera_{camera_index}.npz')
            matrix = data['matrix']
            perspective_matrices.append(matrix)
        except FileNotFoundError:
            print(f"Perspective matrix file not found for camera {camera_index}. Please calibrate the cameras first.")
            exit(1)
    return perspective_matrices

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

def generate_kalman_filters():
    kalman_filter_R = KalmanFilter(constants['DT'], constants['U_X'], constants['U_Y'], constants['STD_ACC'], constants['X_STD_MEAS'], constants['Y_STD_MEAS'])
    kalman_filter_L = KalmanFilter(constants['DT'], constants['U_X'], constants['U_Y'], constants['STD_ACC'], constants['X_STD_MEAS'], constants['Y_STD_MEAS'])
    kalman_filter_C = KalmanFilter(constants['DT'], constants['U_X'], constants['U_Y'], constants['STD_ACC'], constants['X_STD_MEAS'], constants['Y_STD_MEAS'])
    return kalman_filter_R, kalman_filter_L, kalman_filter_C

def get_threshold(cam, t):
    success, t_plus = cam2gray(cam)
    dimg = cv2.absdiff(t, t_plus)
    blur = cv2.GaussianBlur(dimg, (5, 5), 0)
    blur = cv2.bilateralFilter(blur, 9, 75, 75)
    _, thresh = cv2.threshold(blur, 60, 255, 0)
    return thresh



def get_score_coordinates(dart_coordinates, majority_camera_index):
    # Transform the dart coordinates to match the drawn dartboard
    if dart_coordinates is not None:
        x, y = dart_coordinates
        inverse_matrix = cv2.invert(perspective_matrices[majority_camera_index])[1]
        transformed_coords = cv2.perspectiveTransform(np.array([[[x, y]]], dtype=np.float32), inverse_matrix)[0][0]
        dart_coordinates = tuple(map(int, transformed_coords))
        return dart_coordinates
    return None

def takeout_procedure(cam_R, cam_L, cam_C, mode):
    print("Takeout procedure initiated.")

    start_time = time.time()
    # Wait for the specified delay to allow hand removal
    while time.time() - start_time < constants['TAKEOUT_DELAY']:
        cam2gray(cam_R)
        cam2gray(cam_L)
        cam2gray(cam_C)
        time.sleep(0.1)

    print("Takeout procedure completed.")

def calculate_score_from_coordinates(x, y, camera_index):
    inverse_matrix = cv2.invert(perspective_matrices[camera_index])[1]
    transformed_coords = cv2.perspectiveTransform(np.array([[[x, y]]], dtype=np.float32), inverse_matrix)[0][0]
    transformed_x, transformed_y = transformed_coords

    dx = transformed_x - center[0]
    dy = transformed_y - center[1]
    distance_from_center = math.sqrt(dx**2 + dy**2)
    angle = math.atan2(dy, dx)
    score = calculate_score(distance_from_center, angle)
    return score

def getRealLocation(corners_final, mount, prev_tip_point=None, blur=None, kalman_filter=None):
    if mount == "right":
        loc = np.argmax(corners_final, axis=0)
    else:
        loc = np.argmin(corners_final, axis=0)
    locationofdart = corners_final[loc]
    
    # Skeletonize the dart contour
    dart_contour = corners_final.reshape((-1, 1, 2))
    skeleton = cv2.ximgproc.thinning(cv2.drawContours(np.zeros_like(blur), [dart_contour], -1, 255, thickness=cv2.FILLED))
    
    # Detect the dart tip using skeletonization and Kalman filter
    dart_tip = find_dart_tip(skeleton, prev_tip_point, kalman_filter)
    
    if dart_tip is not None:
        tip_x, tip_y = dart_tip
        # Draw a circle around the dart tip
        if blur is not None:
            cv2.circle(blur, (tip_x, tip_y), 5, (0, 255, 0), 2)
        
        locationofdart = dart_tip
    
    return locationofdart, dart_tip

def calculate_score(distance, angle):
    if angle < 0:
        angle += 2 * np.pi
    sector_scores = [10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5, 20, 1, 18, 4, 13, 6]
    sector_index = int(angle / (2 * np.pi) * 20)
    base_score = sector_scores[sector_index]
    if distance <= BULLSEYE_RADIUS_PX:
        return 50
    elif distance <= OUTER_BULL_RADIUS_PX:
        return 25
    elif TRIPLE_RING_INNER_RADIUS_PX < distance <= TRIPLE_RING_OUTER_RADIUS_PX:
        return base_score * 3
    elif DOUBLE_RING_INNER_RADIUS_PX < distance <= DOUBLE_RING_OUTER_RADIUS_PX:
        return base_score * 2
    elif distance <= DOUBLE_RING_OUTER_RADIUS_PX:
        return base_score
    else:
        return 0
        
def find_dart_tip(skeleton, prev_tip_point, kalman_filter):
    # Find the contour of the skeleton
    contours, _ = cv2.findContours(skeleton, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if len(contours) > 0:
        # Find the contour with the maximum area (assuming it represents the dart)
        dart_contour = max(contours, key=cv2.contourArea)

        # Convert the contour to a Shapely Polygon
        dart_polygon = Polygon(dart_contour.reshape(-1, 2))

        # Find the lowest point of the dart contour
        dart_points = dart_polygon.exterior.coords
        lowest_point = max(dart_points, key=lambda x: x[1])

        # Adjust the tip coordinates by half of the tip's diameter
        tip_radius_px = constants['TIP_RADIUS_MM'] * constants['PIXELS_PER_MM']

        # Determine the adjustment direction based on the camera's perspective
        adjustment_direction = 0  # Adjust towards the dartboard center (negative direction)

        # Calculate the adjusted tip coordinates
        adjusted_tip_x = lowest_point[0] + adjustment_direction * tip_radius_px
        adjusted_tip_y = lowest_point[1]

        # Predict the dart tip position using the Kalman filter
        predicted_tip = kalman_filter.predict()
        
        # Update the Kalman filter with the observed dart tip position
        kalman_filter.update(np.array([[adjusted_tip_x], [adjusted_tip_y]]))
        
        return int(adjusted_tip_x), int(adjusted_tip_y)
    
    return None