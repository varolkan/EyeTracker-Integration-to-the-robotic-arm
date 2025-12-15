/*
 * High-Performance 4-DOF Robot Arm Controller
 * For Arduino/ESP32 with Eye-Tracking Integration
 * 
 * Servos: Base Yaw, Shoulder Pitch, Elbow Extension, Gripper
 * Communication: Serial @ 115200 baud
 * Protocol: <S1,S2,S3,S4>\n where S1-S4 are servo angles (0-180)
 * 
 * Features:
 * - Non-blocking serial parsing
 * - Smooth servo movement with interpolation
 * - Angle clamping and safety limits
 * - Low-latency direct writes (option to use VarSpeedServo for smoothing)
 */

#include <Servo.h>

// ============== CONFIGURATION ==============

// Servo pins
const int BASE_PIN = 9;      // Base yaw servo (D9)
const int SHOULDER_PIN = 10; // Shoulder pitch servo (D10)
const int ELBOW_PIN = 11;    // Elbow extension servo (D11)
const int GRIPPER_PIN = 6;   // Gripper servo (D6)

// Servo angle limits (safety constraints)
const int BASE_MIN = 0;
const int BASE_MAX = 180;
const int SHOULDER_MIN = 30;
const int SHOULDER_MAX = 150;
const int ELBOW_MIN = 0;
const int ELBOW_MAX = 180;
const int GRIPPER_MIN = 60;
const int GRIPPER_MAX = 120;

// Smooth movement parameters
const int SMOOTH_STEP = 2;       // Degrees per update step
const int UPDATE_INTERVAL = 15;  // Milliseconds between updates (lower = faster)

// Serial communication
const long BAUD_RATE = 115200;
const int BUFFER_SIZE = 64;
const char START_MARKER = '<';
const char END_MARKER = '>';

// ============== GLOBAL VARIABLES ==============

// Servo objects
Servo baseServo;
Servo shoulderServo;
Servo elbowServo;
Servo gripperServo;

// Current servo positions
int currentBase = 90;
int currentShoulder = 90;
int currentElbow = 90;
int currentGripper = 90;

// Target servo positions (from serial) - volatile for safe concurrent access
volatile int targetBase = 90;
volatile int targetShoulder = 90;
volatile int targetElbow = 90;
volatile int targetGripper = 90;

// Serial parsing
char serialBuffer[BUFFER_SIZE];
int bufferIndex = 0;
boolean newDataAvailable = false;

// Timing for non-blocking smooth movement
unsigned long lastUpdateTime = 0;

// ============== SETUP ==============

void setup() {
  // Initialize serial communication
  Serial.begin(BAUD_RATE);
  
  // Attach servos to pins
  baseServo.attach(BASE_PIN);
  shoulderServo.attach(SHOULDER_PIN);
  elbowServo.attach(ELBOW_PIN);
  gripperServo.attach(GRIPPER_PIN);
  
  // Move to initial positions
  baseServo.write(currentBase);
  shoulderServo.write(currentShoulder);
  elbowServo.write(currentElbow);
  gripperServo.write(currentGripper);
  
  // Wait for servos to reach position
  delay(500);
  
  // Send ready signal
  Serial.println("READY");
  Serial.flush();
}

// ============== MAIN LOOP ==============

void loop() {
  // Read serial data (non-blocking)
  receiveSerialData();
  
  // Parse received data
  if (newDataAvailable) {
    parseSerialData();
    newDataAvailable = false;
  }
  
  // Update servo positions smoothly (non-blocking)
  unsigned long currentTime = millis();
  if (currentTime - lastUpdateTime >= UPDATE_INTERVAL) {
    lastUpdateTime = currentTime;
    updateServoPositions();
  }
  
  // No delay() calls - keeps loop running at maximum speed
}

// ============== SERIAL COMMUNICATION ==============

void receiveSerialData() {
  /*
   * Non-blocking serial data reception
   * Looks for data between START_MARKER '<' and END_MARKER '>'
   */
  while (Serial.available() > 0 && !newDataAvailable) {
    char receivedChar = Serial.read();
    
    if (receivedChar == START_MARKER) {
      // Start of new packet
      bufferIndex = 0;
    }
    else if (receivedChar == END_MARKER) {
      // End of packet
      serialBuffer[bufferIndex] = '\0'; // Null terminate
      newDataAvailable = true;
    }
    else if (bufferIndex < BUFFER_SIZE - 1) {
      // Store character
      serialBuffer[bufferIndex] = receivedChar;
      bufferIndex++;
    }
  }
}

void parseSerialData() {
  /*
   * Parse comma-separated servo angles from buffer
   * Format: S1,S2,S3,S4
   * Example: 90,120,45,100
   */
  int values[4];
  int valueCount = 0;
  
  char* token = strtok(serialBuffer, ",");
  while (token != NULL && valueCount < 4) {
    values[valueCount] = atoi(token);
    valueCount++;
    token = strtok(NULL, ",");
  }
  
  if (valueCount == 4) {
    // Apply safety clamping and update targets
    targetBase = constrain(values[0], BASE_MIN, BASE_MAX);
    targetShoulder = constrain(values[1], SHOULDER_MIN, SHOULDER_MAX);
    targetElbow = constrain(values[2], ELBOW_MIN, ELBOW_MAX);
    targetGripper = constrain(values[3], GRIPPER_MIN, GRIPPER_MAX);
  }
}

// ============== SERVO CONTROL ==============

void updateServoPositions() {
  /*
   * Smoothly interpolate current positions towards target positions
   * Uses small incremental steps for smooth motion
   */
  
  // Update base servo
  currentBase = smoothMove(currentBase, targetBase, SMOOTH_STEP);
  baseServo.write(currentBase);
  
  // Update shoulder servo
  currentShoulder = smoothMove(currentShoulder, targetShoulder, SMOOTH_STEP);
  shoulderServo.write(currentShoulder);
  
  // Update elbow servo
  currentElbow = smoothMove(currentElbow, targetElbow, SMOOTH_STEP);
  elbowServo.write(currentElbow);
  
  // Update gripper servo (faster response for gripper)
  currentGripper = smoothMove(currentGripper, targetGripper, 10);
  gripperServo.write(currentGripper);
}

int smoothMove(int current, int target, int step) {
  /*
   * Move current value towards target by step amount
   * Returns new position
   */
  if (current < target) {
    current += step;
    if (current > target) current = target;
  }
  else if (current > target) {
    current -= step;
    if (current < target) current = target;
  }
  return current;
}

// ============== OPTIONAL: DIRECT WRITE MODE ==============
/*
 * For absolute minimum latency, uncomment this function and call it
 * instead of updateServoPositions() in the main loop.
 * This writes servo positions directly without smoothing.
 */

/*
void directWriteServos() {
  baseServo.write(targetBase);
  shoulderServo.write(targetShoulder);
  elbowServo.write(targetElbow);
  gripperServo.write(targetGripper);
  
  currentBase = targetBase;
  currentShoulder = targetShoulder;
  currentElbow = targetElbow;
  currentGripper = targetGripper;
}
*/
