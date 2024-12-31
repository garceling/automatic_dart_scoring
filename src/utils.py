def load_perspective_matrices():
    perspective_matrices = []
    for camera_index in range(NUM_CAMERAS):
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

def getThreshold(cam, t):
    success, t_plus = cam2gray(cam)
    dimg = cv2.absdiff(t, t_plus)
    blur = cv2.GaussianBlur(dimg, (5, 5), 0)
    blur = cv2.bilateralFilter(blur, 9, 75, 75)
    _, thresh = cv2.threshold(blur, 60, 255, 0)
    return thresh

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

def intialize_cameras():
    
    cam_R = cv2.VideoCapture(0)
    cam_L = cv2.VideoCapture(2)
    cam_C = cv2.VideoCapture(4)

    if not cam_R.isOpened() or not cam_L.isOpened() or not cam_C.isOpened():
        print("Failed to open one or more cameras.")
        sys.exit()

    # Read first image twice to start loop
    _, _ = cam2gray(cam_R)
    _, _ = cam2gray(cam_L)
    _, _ = cam2gray(cam_C)

    time.sleep(0.1)

    success, t_R = cam2gray(cam_R)
    _, t_L = cam2gray(cam_L)
    _, t_C = cam2gray(cam_C)

    return success, cam_R, cam_L, cam_C


def generate_kalman_filters():
    kalman_filter_R = KalmanFilter(DT, U_X, U_Y, STD_ACC, X_STD_MEAS, Y_STD_MEAS)
    kalman_filter_L = KalmanFilter(DT, U_X, U_Y, STD_ACC, X_STD_MEAS, Y_STD_MEAS)
    kalman_filter_C = KalmanFilter(DT, U_X, U_Y, STD_ACC, X_STD_MEAS, Y_STD_MEAS)
    return kalman_filter_R, kalman_filter_L, kalman_filter_C

def get_threshold(cam, t):
    success, t_plus = cam2gray(cam)
    dimg = cv2.absdiff(t, t_plus)
    blur = cv2.GaussianBlur(dimg, (5, 5), 0)
    blur = cv2.bilateralFilter(blur, 9, 75, 75)
    _, thresh = cv2.threshold(blur, 60, 255, 0)
    return thresh


def check_thresholds(cam_R, cam_L, cam_C, t_R, t_L, t_C):
    ''' 
    Counts the number of non-zero pixels in the threshold images. It checks if the nnz is within 
    a range of 1000-7500. This likely indicates a movement ( ie: dart being thrown). There is a upper 
    limit as that could be caused by too much noise/movement
    '''
    thresh_R = get_threshold(cam_R, t_R)
    thresh_L = get_treshold(cam_L, t_L)
    thresh_C = get_threshold(cam_C, t_C)

    non_zero_R = cv2.countNonZero(thresh_R)
    non_zero_L = cv2.countNonZero(thresh_L)
    non_zero_C = cv2.countNonZero(thresh_C)

    if ((1000 < non_zero_R < 7500) or 
        (1000 < non_zero_L < 7500) or 
        (1000 < non_zero_C < 7500)):
        return True, thresh_R, thresh_L, thresh_C

    return False, None, None, None

def corner_detection(blur_R, blur_L, blur_C):
    ''' 
    Applies a diff operation (frame subtraction). followed by a blurring to highlihgt any changes 
    in the frame. It then detects corners (features) in the blurred frame to find the dart
    '''

    corners_R = getCorners(blur_R)
    corners_L = getCorners(blur_L)
    corners_C = getCorners(blur_C)

    if corners_R.size < 40 and corners_L.size < 40 and corners_C.size < 40:
        print("---- Dart Not Detected -----")
        return False, None, None, None
    return True, corners_R, corners_L, corners_C

def filtered_corner_detection(corners_R, corners_L, corners_C):
    corners_f_R = filterCorners(corners_R)
    corners_f_L = filterCorners(corners_L)
    corners_f_C = filterCorners(corners_C)

    if corners_f_R.size < 30 and corners_f_L.size < 30 and corners_f_C.size < 30:
        print("---- Filtered Dart Not Detected -----")
        return False, None, None, None
    return True, corners_f_R, corners_f_L, corners_f_C

def calculate_majority_score(camera_scores):
    score_counts = {}
    for score in camera_scores:
        if score is not None:
            score_counts[score] = score_counts.get(score, 0) + 1

    if score_counts:
        return max(score_counts, key=score_counts.get)

    return None

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
    while time.time() - start_time < TAKEOUT_DELAY:
        cam2gray(cam_R)
        cam2gray(cam_L)
        cam2gray(cam_C)
        time.sleep(0.1)

    print("Takeout procedure completed.")

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
        tip_radius_px = TIP_RADIUS_MM * PIXELS_PER_MM

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