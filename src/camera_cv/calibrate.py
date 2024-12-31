
def select_points_event(event, x, y, flags, param):
    frame, selected_points, camera_index = param
    if event == cv2.EVENT_LBUTTONDOWN and len(selected_points) < 4:
        selected_points.append([x, y])
        cv2.circle(frame, (x, y), 5, (0, 255, 0), -1)
        cv2.imshow(f"Camera {camera_index} - Select 4 Points", frame)
        if len(selected_points) == 4:
            cv2.destroyWindow(f"Camera {camera_index} - Select 4 Points")

def calibrate_camera(camera_index):
    cap = cv2.VideoCapture(camera_index)
    ret, frame = cap.read()
    if ret:
        window_name = f"Camera {camera_index} - Select 4 Points"
        cv2.namedWindow(window_name)
        cv2.imshow(window_name, frame)
        
        selected_points = []
        cv2.setMouseCallback(window_name, select_points_event, (frame, selected_points, camera_index))
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        cap.release()

        if len(selected_points) == 4:
            return np.float32(selected_points)
    return None

def calibrate(self):
    messagebox.showinfo("Calibration", "Please select 4 points on each camera feed.")
    
    # Define the drawn_points variable
    global drawn_points
    drawn_points = np.float32([
        [center[0], center[1] - DOUBLE_RING_OUTER_RADIUS_PX],
        [center[0] + DOUBLE_RING_OUTER_RADIUS_PX, center[1]],
        [center[0], center[1] + DOUBLE_RING_OUTER_RADIUS_PX],
        [center[0] - DOUBLE_RING_OUTER_RADIUS_PX, center[1]],
    ])
    
    for camera_index in range(NUM_CAMERAS):
        live_feed_points = calibrate_camera(camera_index)
        if live_feed_points is not None:
            M = cv2.getPerspectiveTransform(drawn_points, live_feed_points)
            perspective_matrices.append(M)
            np.savez(f'perspective_matrix_camera_{camera_index}.npz', matrix=M)
        else:
            messagebox.showerror("Calibration Error", f"Failed to calibrate camera {camera_index}")
            return

    messagebox.showinfo("Calibration", "Calibration completed successfully.")
