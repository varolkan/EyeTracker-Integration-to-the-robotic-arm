"""
Test script for eye tracking functionality
Tests the eye tracking 5 times as required
"""

import cv2
import numpy as np
import mediapipe as mp
import time

# Initialize MediaPipe
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# Eye landmark indices
LEFT_EYE_INDICES = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_INDICES = [362, 385, 387, 263, 373, 380]
LEFT_IRIS_INDICES = [474, 475, 476, 477]
RIGHT_IRIS_INDICES = [469, 470, 471, 472]

def get_iris_position(landmarks, iris_indices, frame_width, frame_height):
    """Get normalized iris position"""
    iris_coords = []
    for idx in iris_indices:
        landmark = landmarks[idx]
        iris_coords.append([landmark.x * frame_width, landmark.y * frame_height])
    return np.mean(iris_coords, axis=0)

def calculate_gaze_direction(landmarks, frame_width, frame_height):
    """Calculate gaze direction from iris positions"""
    left_iris = get_iris_position(landmarks, LEFT_IRIS_INDICES, frame_width, frame_height)
    right_iris = get_iris_position(landmarks, RIGHT_IRIS_INDICES, frame_width, frame_height)
    
    # Get eye corners for reference
    left_eye_coords = []
    right_eye_coords = []
    
    for idx in LEFT_EYE_INDICES:
        landmark = landmarks[idx]
        left_eye_coords.append([landmark.x * frame_width, landmark.y * frame_height])
    
    for idx in RIGHT_EYE_INDICES:
        landmark = landmarks[idx]
        right_eye_coords.append([landmark.x * frame_width, landmark.y * frame_height])
    
    left_eye_center = np.mean(left_eye_coords, axis=0)
    right_eye_center = np.mean(right_eye_coords, axis=0)
    
    # Calculate gaze offset
    left_offset = left_iris - left_eye_center
    right_offset = right_iris - right_eye_center
    avg_offset = (left_offset + right_offset) / 2.0
    
    # Normalize
    eye_width = np.linalg.norm(right_eye_center - left_eye_center)
    gaze_x = avg_offset[0] / (eye_width * 0.5)
    gaze_y = avg_offset[1] / (eye_width * 0.5)
    
    # Clamp
    gaze_x = max(-1.0, min(1.0, gaze_x))
    gaze_y = max(-1.0, min(1.0, gaze_y))
    
    # Depth estimate
    depth_estimate = eye_width / frame_width
    depth_estimate = max(0.0, min(1.0, depth_estimate))
    
    return gaze_x, gaze_y, depth_estimate

def test_eye_tracking(test_number, duration=10):
    """Run a single eye tracking test"""
    print(f"\n{'='*60}")
    print(f"TEST {test_number}/5")
    print(f"{'='*60}")
    print(f"Duration: {duration} seconds")
    print("Look around to test gaze tracking...")
    print("Press 'q' to quit early\n")
    
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    if not cap.isOpened():
        print("ERROR: Cannot open camera")
        return False
    
    start_time = time.time()
    frame_count = 0
    detection_count = 0
    gaze_readings = []
    
    while time.time() - start_time < duration:
        ret, frame = cap.read()
        if not ret:
            print("ERROR: Cannot read frame")
            break
        
        frame_height, frame_width = frame.shape[:2]
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(rgb_frame)
        
        frame_count += 1
        
        if results.multi_face_landmarks:
            detection_count += 1
            face_landmarks = results.multi_face_landmarks[0].landmark
            
            # Calculate gaze
            gaze_x, gaze_y, depth = calculate_gaze_direction(face_landmarks, frame_width, frame_height)
            gaze_readings.append((gaze_x, gaze_y, depth))
            
            # Visualize
            left_iris = get_iris_position(face_landmarks, LEFT_IRIS_INDICES, frame_width, frame_height)
            right_iris = get_iris_position(face_landmarks, RIGHT_IRIS_INDICES, frame_width, frame_height)
            
            cv2.circle(frame, tuple(left_iris.astype(int)), 3, (255, 0, 255), -1)
            cv2.circle(frame, tuple(right_iris.astype(int)), 3, (255, 0, 255), -1)
            
            # Display info
            elapsed = int(time.time() - start_time)
            remaining = duration - elapsed
            
            cv2.putText(frame, f"Test {test_number}/5 - Time: {remaining}s", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(frame, f"Gaze X: {gaze_x:+.3f}", (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.putText(frame, f"Gaze Y: {gaze_y:+.3f}", (10, 90),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.putText(frame, f"Depth:  {depth:.3f}", (10, 120),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.putText(frame, f"Detection: {detection_count}/{frame_count}", (10, 150),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        else:
            cv2.putText(frame, "No face detected", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        cv2.imshow(f'Eye Tracking Test {test_number}', frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("\nTest interrupted by user")
            break
    
    cap.release()
    cv2.destroyAllWindows()
    
    # Calculate statistics
    detection_rate = (detection_count / frame_count * 100) if frame_count > 0 else 0
    fps = frame_count / duration
    
    print(f"\nTest Results:")
    print(f"  Frames processed: {frame_count}")
    print(f"  Faces detected: {detection_count}")
    print(f"  Detection rate: {detection_rate:.1f}%")
    print(f"  Average FPS: {fps:.1f}")
    
    if gaze_readings:
        gaze_x_vals = [g[0] for g in gaze_readings]
        gaze_y_vals = [g[1] for g in gaze_readings]
        depth_vals = [g[2] for g in gaze_readings]
        
        print(f"\nGaze Statistics:")
        print(f"  X range: [{min(gaze_x_vals):.3f}, {max(gaze_x_vals):.3f}]")
        print(f"  Y range: [{min(gaze_y_vals):.3f}, {max(gaze_y_vals):.3f}]")
        print(f"  Depth range: [{min(depth_vals):.3f}, {max(depth_vals):.3f}]")
        print(f"  X std dev: {np.std(gaze_x_vals):.3f}")
        print(f"  Y std dev: {np.std(gaze_y_vals):.3f}")
    
    success = detection_rate > 80  # Consider test successful if >80% detection
    
    if success:
        print(f"\n✓ TEST {test_number} PASSED")
    else:
        print(f"\n✗ TEST {test_number} FAILED (Low detection rate)")
    
    return success

def main():
    """Run all 5 tests"""
    print("="*60)
    print("EYE TRACKING TEST SUITE")
    print("="*60)
    print("\nThis will run 5 eye tracking tests of 10 seconds each.")
    print("Make sure your face is visible to the camera.")
    print("\nPress Enter to start...")
    input()
    
    results = []
    
    for i in range(1, 6):
        time.sleep(2)  # Pause between tests
        success = test_eye_tracking(i, duration=10)
        results.append(success)
    
    # Final summary
    print("\n" + "="*60)
    print("FINAL RESULTS")
    print("="*60)
    
    for i, success in enumerate(results, 1):
        status = "✓ PASSED" if success else "✗ FAILED"
        print(f"Test {i}: {status}")
    
    passed = sum(results)
    print(f"\nTotal: {passed}/5 tests passed")
    
    if passed == 5:
        print("\n🎉 ALL TESTS PASSED! Eye tracking is working correctly.")
    elif passed >= 3:
        print("\n⚠ MOST TESTS PASSED. Some issues detected but generally working.")
    else:
        print("\n❌ TESTS FAILED. Please check camera and lighting conditions.")
    
    face_mesh.close()

if __name__ == "__main__":
    main()
