# Robot Arm Wiring Diagram and Setup Guide

## Hardware Components
- Arduino Uno/Mega or ESP32 development board
- 4x Servo motors (SG90 or similar for small arms, MG995 for larger loads)
- External 5V-6V power supply (2A minimum per servo, 5A+ recommended)
- Capacitors: 1000µF electrolytic (per servo) + 0.1µF ceramic
- Logic level shifter (if using 5V servos with 3.3V ESP32)
- USB cable for Arduino programming and serial communication

## Servo Connections

### Pin Assignments
```
Base Yaw Servo:      Pin D9  (PWM)
Shoulder Pitch Servo: Pin D10 (PWM)
Elbow Extension Servo: Pin D11 (PWM)
Gripper Servo:       Pin D6  (PWM)
```

### Individual Servo Wiring (for each of the 4 servos)
```
Servo Wire Colors (Standard):
  Brown/Black:  Ground (GND)
  Red:          Power (VCC - 5V to 6V)
  Orange/Yellow: Signal (PWM control from Arduino)

Connection:
  Servo GND    → External Power Supply GND + Arduino GND (common ground!)
  Servo VCC    → External Power Supply (+5V/6V) with 1000µF capacitor
  Servo Signal → Arduino PWM pin (see above)
```

## Power Supply Setup

### CRITICAL: Separate Power for Servos
```
External Power Supply (5-6V, 5A+):
  (+) Positive → Servo VCC rails (all 4 servos)
  (-) Ground   → Arduino GND (MUST share common ground)
                 → Servo GND rails (all 4 servos)

Arduino Power:
  USB Power    → Arduino (for logic and communication)
  
NEVER power servos from Arduino 5V pin! 
Arduino's onboard regulator cannot provide enough current.
```

### Power Distribution Board (Recommended)
```
Create a simple power distribution board:

[External 5-6V PSU]
        |
        +--[1000µF Cap]--+
        |                |
        +-- Servo 1 VCC  |
        +-- Servo 2 VCC  |
        +-- Servo 3 VCC  |
        +-- Servo 4 VCC  |
        |                |
    [Common GND]  [Arduino GND]
```

## Decoupling and Filtering

### Capacitor Placement
```
1. Bulk Capacitance (1000µF electrolytic):
   - Place one 1000µF capacitor across the power supply output
   - Polarity: (+) to VCC, (-) to GND
   - This smooths out large current draws

2. Bypass Capacitors (0.1µF ceramic):
   - Place one 0.1µF capacitor near each servo's power pins
   - These filter high-frequency noise
   - No polarity concern (ceramic)

Physical Layout:
  PSU (+) ---[1000µF]--- Servo VCC
             |
          [0.1µF] near each servo
             |
  PSU (-) ------------------- Servo GND
```

## Logic Level Shifting (ESP32 Only)

### If using ESP32 (3.3V logic) with 5V servos:
```
Standard SG90/MG995 servos work with 3.3V signals, but for reliability:

Option 1: Direct Connection (usually works)
  ESP32 GPIO → Servo Signal
  
Option 2: Level Shifter (more reliable)
  ESP32 GPIO → Level Shifter (LV side)
  Level Shifter (HV side) → Servo Signal
  Level Shifter HV → 5V
  Level Shifter LV → 3.3V
  Common GND

Popular Level Shifters:
  - 4-channel bidirectional BSS138-based shifter
  - TXS0108E 8-channel shifter
```

## Complete Wiring Diagram

```
                         [External 5-6V PSU (5A+)]
                                |
                    +-----------+------------+
                    |                        |
                [1000µF Cap]            [Common GND]
                    |                        |
        +-----------+-----------+            |
        |           |           |            |
    [Servo 1]   [Servo 2]   [Servo 3]   [Servo 4]
     (Base)    (Shoulder)   (Elbow)   (Gripper)
        |           |           |            |
      VCC         VCC         VCC          VCC
      GND         GND         GND          GND
      SIG         SIG         SIG          SIG
        |           |           |            |
        +-----+-----+-----+-----+            |
              |           |                  |
              |      [0.1µF Caps]            |
              |           |                  |
              +-----------+------------------+
                          |
                    [Common GND]
                          |
                    [Arduino GND]
                          
[Arduino/ESP32]
  D9  → Base Servo Signal
  D10 → Shoulder Servo Signal  
  D11 → Elbow Servo Signal
  D6  → Gripper Servo Signal
  GND → Common Ground
  USB → Computer (for programming & serial)
```

## Assembly Instructions

### Step 1: Power Setup
1. Connect external PSU ground to a common ground rail
2. Connect Arduino GND to the same common ground rail
3. Solder 1000µF capacitor across PSU output (observe polarity!)
4. Test voltage: should read 5-6V between VCC and GND

### Step 2: Servo Connections
1. Connect all servo GND wires to common ground
2. Connect all servo VCC wires to PSU positive (through cap)
3. Add 0.1µF ceramic caps near each servo's power pins
4. Connect servo signal wires to Arduino PWM pins:
   - Base → D9
   - Shoulder → D10
   - Elbow → D11
   - Gripper → D6

### Step 3: Safety Check
Before powering on:
- [ ] Verify all grounds are connected (PSU, Arduino, servos)
- [ ] Verify servos are NOT connected to Arduino 5V pin
- [ ] Check capacitor polarity (if using electrolytic)
- [ ] Check for short circuits with multimeter
- [ ] Verify signal wires are connected to PWM pins

### Step 4: Initial Testing
1. Upload Arduino sketch first (servos will center at 90°)
2. Power Arduino via USB
3. Power external PSU (servos should move to center position)
4. Test with Python script

## Troubleshooting

### Servos jittering or not moving smoothly
- Add more/larger capacitors
- Check power supply current rating (needs 2A per servo minimum)
- Reduce SMOOTH_STEP in Arduino code
- Check for loose connections

### Servos not responding
- Verify common ground connection
- Check signal wire connections
- Test servo with servo tester or Arduino servo sweep example
- Verify PWM pins are correct

### Arduino resets when servos move
- Servos are drawing power from Arduino (bad!)
- Ensure servos are powered from external supply
- Check ground connection

### ESP32 specific issues
- Use separate power supply for ESP32 (not from servo PSU)
- Consider level shifter for signal lines
- Check if GPIO pins are PWM-capable

## Safety Considerations

1. **Current Capacity**: Each servo can draw 0.5-2A under load. Ensure PSU can handle total load.

2. **Mechanical Limits**: Set software limits in Arduino code to prevent mechanical damage:
   ```cpp
   const int BASE_MIN = 0;      // Adjust based on your arm
   const int BASE_MAX = 180;
   ```

3. **Emergency Stop**: Keep USB cable accessible to quickly disconnect Arduino

4. **Heat Management**: High-torque servos can overheat. Monitor temperature during extended use.

5. **Secure Mounting**: Ensure arm is securely mounted to prevent tipping

## Recommended Parts List

### Essential Components
- Arduino Uno ($25) or ESP32 DevKit ($10)
- 4x SG90 servos ($2 each, $8 total) for small arms
- OR 4x MG995 servos ($8 each, $32 total) for stronger arms
- 5V 5A power supply ($10)
- Capacitor kit ($10): 1000µF electrolytics + 0.1µF ceramics
- Jumper wires ($5)
- Breadboard or protoboard ($5)

### Optional but Recommended
- Logic level shifter for ESP32 ($2)
- Servo tester for debugging ($5)
- Buck converter for adjustable voltage ($5)
- Heat sinks for servos ($5)
- Mechanical arm kit ($20-50)

**Total Cost: $50-100 depending on servo choice**

## Pin Configuration for Different Boards

### Arduino Uno/Nano
```
Base:     D9  (Timer1)
Shoulder: D10 (Timer1)
Elbow:    D11 (Timer2)
Gripper:  D6  (Timer0 - avoid D5/D6 if using delay())
```

### Arduino Mega
```
Base:     D9  (Timer2)
Shoulder: D10 (Timer2)
Elbow:    D11 (Timer1)
Gripper:  D6  (Timer4)
```

### ESP32
```
Base:     GPIO 18 (LEDC Channel 0)
Shoulder: GPIO 19 (LEDC Channel 1)
Elbow:    GPIO 21 (LEDC Channel 2)
Gripper:  GPIO 22 (LEDC Channel 3)
```
Note: Update pin numbers in Arduino code if using ESP32

## Serial Connection

### USB Connection
```
Computer USB → Arduino/ESP32 USB Port
Baud Rate: 115200
Protocol: <S1,S2,S3,S4>\n
```

### Finding Your Port
**Windows**: Check Device Manager → Ports (COM & LPT)
- Usually COM3, COM4, etc.

**Linux**: Check `/dev/ttyUSB*` or `/dev/ttyACM*`
```bash
ls /dev/tty*
# or
python -m serial.tools.list_ports
```

**Mac**: Check `/dev/cu.usbserial*` or `/dev/cu.usbmodem*`
```bash
ls /dev/cu.*
```

Update the `SERIAL_PORT` variable in `robot_arm_controller.py` accordingly.

## Testing Procedure

### 1. Servo Test (without eye tracking)
```python
# Simple test script
import serial
import time

ser = serial.Serial('COM3', 115200, timeout=1)
time.sleep(2)

# Test each servo
ser.write(b'<90,90,90,90>\n')  # Center all
time.sleep(1)
ser.write(b'<0,90,90,90>\n')   # Base left
time.sleep(1)
ser.write(b'<180,90,90,90>\n') # Base right
time.sleep(1)
ser.write(b'<90,30,90,90>\n')  # Shoulder up
time.sleep(1)
ser.write(b'<90,150,90,90>\n') # Shoulder down
```

### 2. Full System Test
1. Run Arduino sketch
2. Run Python eye tracker: `python robot_arm_controller.py`
3. Look around to test servo movements
4. Blink to test gripper control

## Advanced: VarSpeedServo Library (Optional)

For even smoother motion with speed control:

### Installation
```bash
# Arduino IDE: Sketch → Include Library → Manage Libraries
# Search for "VarSpeedServo" and install
```

### Modified Arduino Code
```cpp
#include <VarSpeedServo.h>

VarSpeedServo baseServo;
// ... attach and use with speed parameter
baseServo.write(angle, speed); // speed in degrees/second
```

This allows ultra-smooth motion but may add slight latency.
