"""
High-Performance Eye-Tracking Robot Arm Controller
4-DOF Robot Arm Control: Base Yaw, Shoulder Pitch, Elbow Extension, Gripper
Uses MediaPipe Face Mesh/Iris for gaze tracking with low-latency serial communication
"""

import cv2
import numpy as np
import mediapipe as mp
import serial
import time
import threading
from collections import deque
from queue import Queue, Full
import math
import argparse
import os

# ============== CONFIGURATION ==============
SERIAL_PORT = os.environ.get('ROBOT_SERIAL_PORT', 'COM3')  # Configurable via environment variable
BAUD_RATE = 115200    # High baud rate for low latency
CAMERA_INDEX = 0

# Servo angle limits (safety constraints)
BASE_MIN, BASE_MAX = 0, 180          # Base yaw servo
SHOULDER_MIN, SHOULDER_MAX = 30, 150  # Shoulder pitch servo
ELBOW_MIN, ELBOW_MAX = 0, 180        # Elbow extension servo
GRIPPER_OPEN, GRIPPER_CLOSE = 60, 120  # Gripper servo positions

# Filtering parameters
EMA_ALPHA = 0.3  # Exponential Moving Average smoothing factor (0-1, lower = smoother)
FILTER_WINDOW = 5  # Additional moving average window

# Blink detection parameters
BLINK_EAR_THRESHOLD = 0.21  # Eye Aspect Ratio threshold for blink detection
BLINK_CONSEC_FRAMES = 2     # Consecutive frames for blink confirmation
DOUBLE_BLINK_TIME = 0.6     # Time window for double blink (seconds)
DWELL_TIME = 1.5            # Long dwell time for gripper toggle (seconds)

# Gaze mapping parameters
GAZE_X_SENSITIVITY = 90.0   # Maps gaze X (-1 to 1) to base angle range
GAZE_Y_SENSITIVITY = 60.0   # Maps gaze Y (-1 to 1) to shoulder angle range
DEPTH_SENSITIVITY = 90.0    # Maps depth to elbow angle range

# ============== GLOBAL STATE ==============
class RobotState:
    def __init__(self):
        self.base_angle = 90      # Center position
        self.shoulder_angle = 90  # Center position
        self.elbow_angle = 90     # Center position
        self.gripper_open = True  # Gripper state
        
        # Filtering buffers
        self.base_buffer = deque(maxlen=FILTER_WINDOW)
        self.shoulder_buffer = deque(maxlen=FILTER_WINDOW)
        self.elbow_buffer = deque(maxlen=FILTER_WINDOW)
        
        # EMA filtered values
        self.base_ema = 90.0
        self.shoulder_ema = 90.0
        self.elbow_ema = 90.0
        
        # Blink detection
        self.blink_counter = 0
        self.last_blink_time = 0
        self.blink_count = 0
        self.dwell_start_time = None
        
        self.lock = threading.Lock()

robot = RobotState()
command_queue = Queue(maxsize=10)

# ============== MEDIAPIPE SETUP ==============
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# Eye landmark indices for MediaPipe Face Mesh
LEFT_EYE_INDICES = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_INDICES = [362, 385, 387, 263, 373, 380]
LEFT_IRIS_INDICES = [474, 475, 476, 477]
RIGHT_IRIS_INDICES = [469, 470, 471, 472]

# ============== HELPER FUNCTIONS ==============

def clamp(value, min_val, max_val):
    """Clamp value between min and max"""
    return max(min_val, min(max_val, value))

def calculate_ear(eye_landmarks):
    """Calculate Eye Aspect Ratio for blink detection"""
    # Vertical eye distances
    A = np.linalg.norm(eye_landmarks[1] - eye_landmarks[5])
    B = np.linalg.norm(eye_landmarks[2] - eye_landmarks[4])
    # Horizontal eye distance
    C = np.linalg.norm(eye_landmarks[0] - eye_landmarks[3])
    # Eye Aspect Ratio
    ear = (A + B) / (2.0 * C)
    return ear

def extract_eye_landmarks(landmarks, indices, frame_width, frame_height):
    """Extract eye landmark coordinates"""
    coords = []
    for idx in indices:
        landmark = landmarks[idx]
        x = landmark.x * frame_width
        y = landmark.y * frame_height
        coords.append([x, y])
    return np.array(coords)

def get_iris_position(landmarks, iris_indices, frame_width, frame_height):
    """Get normalized iris position (center of iris landmarks)"""
    iris_coords = []
    for idx in iris_indices:
        landmark = landmarks[idx]
        iris_coords.append([landmark.x * frame_width, landmark.y * frame_height])
    return np.mean(iris_coords, axis=0)

def calculate_gaze_direction(landmarks, frame_width, frame_height):
    """
    Calculate gaze direction from iris positions
    Returns: (gaze_x, gaze_y, depth_estimate)
    gaze_x, gaze_y: normalized -1 to 1 (left to right, up to down)
    depth_estimate: normalized 0 to 1 (far to near)
    """
    # Get iris centers
    left_iris = get_iris_position(landmarks, LEFT_IRIS_INDICES, frame_width, frame_height)
    right_iris = get_iris_position(landmarks, RIGHT_IRIS_INDICES, frame_width, frame_height)
    
    # Get eye corners for reference
    left_eye = extract_eye_landmarks(landmarks, LEFT_EYE_INDICES, frame_width, frame_height)
    right_eye = extract_eye_landmarks(landmarks, RIGHT_EYE_INDICES, frame_width, frame_height)
    
    # Calculate eye centers (geometric mean of corners)
    left_eye_center = np.mean(left_eye, axis=0)
    right_eye_center = np.mean(right_eye, axis=0)
    
    # Calculate gaze offset from eye centers
    left_offset = left_iris - left_eye_center
    right_offset = right_iris - right_eye_center
    
    # Average offsets
    avg_offset = (left_offset + right_offset) / 2.0
    
    # Normalize to -1 to 1 range
    eye_width = np.linalg.norm(right_eye_center - left_eye_center)
    gaze_x = avg_offset[0] / (eye_width * 0.5)
    gaze_y = avg_offset[1] / (eye_width * 0.5)
    
    # Clamp to reasonable range
    gaze_x = clamp(gaze_x, -1.0, 1.0)
    gaze_y = clamp(gaze_y, -1.0, 1.0)
    
    # Estimate depth from inter-eye distance (larger = closer to camera)
    depth_estimate = eye_width / frame_width
    depth_estimate = clamp(depth_estimate, 0.0, 1.0)
    
    return gaze_x, gaze_y, depth_estimate

def apply_ema_filter(current_value, new_value, alpha):
    """Apply Exponential Moving Average filter"""
    return alpha * new_value + (1 - alpha) * current_value

def apply_moving_average(buffer, new_value):
    """Apply moving average filter with buffer"""
    buffer.append(new_value)
    return sum(buffer) / len(buffer)

def map_gaze_to_angles(gaze_x, gaze_y, depth):
    """
    Map gaze coordinates to servo angles
    gaze_x -> base yaw (left-right)
    gaze_y -> shoulder pitch (up-down)
    depth -> elbow extension (near-far)
    """
    # Base: map gaze_x from [-1, 1] to servo range
    base_center = (BASE_MIN + BASE_MAX) / 2
    base_angle = base_center + (gaze_x * GAZE_X_SENSITIVITY)
    base_angle = clamp(base_angle, BASE_MIN, BASE_MAX)
    
    # Shoulder: map gaze_y from [-1, 1] to servo range (inverted)
    shoulder_center = (SHOULDER_MIN + SHOULDER_MAX) / 2
    shoulder_angle = shoulder_center - (gaze_y * GAZE_Y_SENSITIVITY)
    shoulder_angle = clamp(shoulder_angle, SHOULDER_MIN, SHOULDER_MAX)
    
    # Elbow: map depth from [0, 1] to servo range
    elbow_angle = ELBOW_MIN + (depth * DEPTH_SENSITIVITY)
    elbow_angle = clamp(elbow_angle, ELBOW_MIN, ELBOW_MAX)
    
    return base_angle, shoulder_angle, elbow_angle

def detect_blink(ear_left, ear_right):
    """
    Detect blinks and differentiate between double-blink and long dwell
    Returns: 'double_blink', 'dwell', or None
    """
    avg_ear = (ear_left + ear_right) / 2.0
    current_time = time.time()
    
    # Check if eye is closed
    if avg_ear < BLINK_EAR_THRESHOLD:
        robot.blink_counter += 1
        if robot.dwell_start_time is None:
            robot.dwell_start_time = current_time
    else:
        # Eye opened
        if robot.blink_counter >= BLINK_CONSEC_FRAMES:
            # Blink confirmed
            dwell_duration = current_time - robot.dwell_start_time if robot.dwell_start_time else 0
            
            if dwell_duration > DWELL_TIME:
                # Long dwell detected
                robot.blink_counter = 0
                robot.dwell_start_time = None
                robot.blink_count = 0
                robot.last_blink_time = current_time
                return 'dwell'
            else:
                # Quick blink
                if current_time - robot.last_blink_time < DOUBLE_BLINK_TIME:
                    # Second blink within time window
                    robot.blink_count += 1
                    if robot.blink_count >= 2:
                        robot.blink_count = 0
                        robot.last_blink_time = current_time
                        robot.blink_counter = 0
                        robot.dwell_start_time = None
                        return 'double_blink'
                else:
                    # First blink
                    robot.blink_count = 1
                    robot.last_blink_time = current_time
        
        robot.blink_counter = 0
        robot.dwell_start_time = None
    
    return None

# ============== SERIAL COMMUNICATION ==============

def serial_sender_thread(port, baud_rate):
    """Thread for sending commands to Arduino/ESP32"""
    try:
        ser = serial.Serial(port, baud_rate, timeout=0.1)
        time.sleep(2)  # Wait for Arduino to initialize
        print(f"Serial connection established on {port} at {baud_rate} baud")
    except Exception as e:
        print(f"Error opening serial port: {e}")
        return
    
    while True:
        try:
            if not command_queue.empty():
                command = command_queue.get()
                ser.write(command.encode())
                ser.flush()
        except Exception as e:
            print(f"Serial send error: {e}")
            time.sleep(0.1)

def send_servo_command(base, shoulder, elbow, gripper):
    """
    Send packetized servo angles to Arduino
    Format: <S1,S2,S3,S4>\n
    """
    command = f"<{int(base)},{int(shoulder)},{int(elbow)},{int(gripper)}>\n"
    try:
        command_queue.put_nowait(command)
    except Full:
        pass  # Queue full, skip this command

# ============== MAIN PROCESSING ==============

def process_frame(frame):
    """Process a single frame for gaze tracking and servo control"""
    frame_height, frame_width = frame.shape[:2]
    
    # Convert to RGB for MediaPipe
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = face_mesh.process(rgb_frame)
    
    if results.multi_face_landmarks:
        face_landmarks = results.multi_face_landmarks[0].landmark
        
        # Extract eye landmarks for blink detection
        left_eye = extract_eye_landmarks(face_landmarks, LEFT_EYE_INDICES, frame_width, frame_height)
        right_eye = extract_eye_landmarks(face_landmarks, RIGHT_EYE_INDICES, frame_width, frame_height)
        
        # Calculate Eye Aspect Ratio
        ear_left = calculate_ear(left_eye)
        ear_right = calculate_ear(right_eye)
        
        # Detect blinks
        blink_event = detect_blink(ear_left, ear_right)
        if blink_event == 'double_blink' or blink_event == 'dwell':
            robot.gripper_open = not robot.gripper_open
            print(f"Gripper toggled: {'OPEN' if robot.gripper_open else 'CLOSED'}")
        
        # Calculate gaze direction
        gaze_x, gaze_y, depth = calculate_gaze_direction(face_landmarks, frame_width, frame_height)
        
        # Map to servo angles
        base_raw, shoulder_raw, elbow_raw = map_gaze_to_angles(gaze_x, gaze_y, depth)
        
        # Apply filters
        with robot.lock:
            # Moving average
            base_ma = apply_moving_average(robot.base_buffer, base_raw)
            shoulder_ma = apply_moving_average(robot.shoulder_buffer, shoulder_raw)
            elbow_ma = apply_moving_average(robot.elbow_buffer, elbow_raw)
            
            # EMA filter
            robot.base_ema = apply_ema_filter(robot.base_ema, base_ma, EMA_ALPHA)
            robot.shoulder_ema = apply_ema_filter(robot.shoulder_ema, shoulder_ma, EMA_ALPHA)
            robot.elbow_ema = apply_ema_filter(robot.elbow_ema, elbow_ma, EMA_ALPHA)
            
            # Update angles
            robot.base_angle = int(robot.base_ema)
            robot.shoulder_angle = int(robot.shoulder_ema)
            robot.elbow_angle = int(robot.elbow_ema)
        
        # Determine gripper position
        gripper_angle = GRIPPER_OPEN if robot.gripper_open else GRIPPER_CLOSE
        
        # Send command to Arduino
        send_servo_command(robot.base_angle, robot.shoulder_angle, robot.elbow_angle, gripper_angle)
        
        # Visualize on frame
        cv2.putText(frame, f"Base: {robot.base_angle}", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, f"Shoulder: {robot.shoulder_angle}", (10, 60), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, f"Elbow: {robot.elbow_angle}", (10, 90), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, f"Gripper: {'OPEN' if robot.gripper_open else 'CLOSED'}", (10, 120), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, f"Gaze: ({gaze_x:.2f}, {gaze_y:.2f})", (10, 150), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        
        # Draw eye landmarks
        for eye in [left_eye, right_eye]:
            for point in eye:
                cv2.circle(frame, tuple(point.astype(int)), 2, (0, 255, 255), -1)
        
        # Draw iris centers
        left_iris = get_iris_position(face_landmarks, LEFT_IRIS_INDICES, frame_width, frame_height)
        right_iris = get_iris_position(face_landmarks, RIGHT_IRIS_INDICES, frame_width, frame_height)
        cv2.circle(frame, tuple(left_iris.astype(int)), 3, (255, 0, 255), -1)
        cv2.circle(frame, tuple(right_iris.astype(int)), 3, (255, 0, 255), -1)
    
    return frame

def main():
    """Main function"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Eye-Tracking Robot Arm Controller')
    parser.add_argument('--port', type=str, default=SERIAL_PORT,
                       help='Serial port for Arduino (default: COM3 or ROBOT_SERIAL_PORT env var)')
    parser.add_argument('--baud', type=int, default=BAUD_RATE,
                       help='Baud rate (default: 115200)')
    parser.add_argument('--camera', type=int, default=CAMERA_INDEX,
                       help='Camera index (default: 0)')
    args = parser.parse_args()
    
    # Start serial communication thread
    serial_thread = threading.Thread(target=serial_sender_thread, 
                                    args=(args.port, args.baud), 
                                    daemon=True)
    serial_thread.start()
    
    # Open camera
    cap = cv2.VideoCapture(args.camera)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)
    
    if not cap.isOpened():
        print("Error: Cannot open camera")
        return
    
    print("Eye-Tracking Robot Arm Controller Started")
    print("Controls:")
    print("  - Look around to move base and shoulder")
    print("  - Move head forward/backward to control elbow")
    print("  - Double blink or long dwell to toggle gripper")
    print("  - Press 'q' to quit")
    
    fps_time = time.time()
    frame_count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Cannot read frame")
            break
        
        # Process frame
        processed_frame = process_frame(frame)
        
        # Calculate FPS
        frame_count += 1
        if time.time() - fps_time > 1.0:
            fps = frame_count / (time.time() - fps_time)
            frame_count = 0
            fps_time = time.time()
            cv2.putText(processed_frame, f"FPS: {fps:.1f}", (10, frame.shape[0] - 20), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        # Display
        cv2.imshow('Eye-Tracking Robot Arm Controller', processed_frame)
        
        # Check for quit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    # Cleanup
    cap.release()
    cv2.destroyAllWindows()
    face_mesh.close()

if __name__ == "__main__":
    main()
