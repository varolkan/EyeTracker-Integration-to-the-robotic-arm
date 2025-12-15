# Quick Start Guide - Eye-Tracking Robot Arm

## 5-Minute Setup

### Hardware (5 minutes)
1. Connect servos to Arduino:
   - Base → Pin D9
   - Shoulder → Pin D10  
   - Elbow → Pin D11
   - Gripper → Pin D6

2. Power:
   - Servo power → External 5-6V supply
   - Arduino → USB
   - Connect all grounds together ⚠️

3. Upload firmware:
   ```bash
   # Open robot_arm_arduino.ino in Arduino IDE
   # Click Upload
   ```

### Software (5 minutes)
1. Install dependencies:
   ```bash
   pip install -r requirements_robot.txt
   ```

2. Find your serial port:
   - **Windows**: Check Device Manager (e.g., COM3)
   - **Linux**: `ls /dev/ttyUSB*` or `/dev/ttyACM*`
   - **Mac**: `ls /dev/cu.*`

3. Run the controller:
   ```bash
   python robot_arm_controller.py --port COM3
   ```

## Usage

### Controls
- **Look left/right** → Base rotates
- **Look up/down** → Shoulder moves
- **Move head forward/back** → Elbow extends/retracts
- **Double blink** → Toggle gripper
- **Press 'q'** → Quit

### First Test
1. Center your face in camera view
2. Look left → Base should rotate left
3. Look right → Base should rotate right
4. Blink twice quickly → Gripper should toggle

## Troubleshooting

### Servos not moving
- Check power supply is connected
- Verify serial port in command
- Check Arduino shows "READY" in Serial Monitor

### Jerky movement
- Adjust filtering: Lower `EMA_ALPHA` in code
- Increase power supply capacity
- Add larger capacitors

### Poor tracking
- Improve lighting
- Look directly at camera
- Reduce sensitivity values

## Safety

⚠️ **IMPORTANT**
- NEVER power servos from Arduino 5V pin
- Keep all grounds connected
- Test in safe area away from people
- Keep finger on 'q' key for emergency stop

## Files Reference

- `ROBOT_ARM_README.md` - Complete guide
- `WIRING_DIAGRAM.md` - Detailed hardware setup
- `IMPLEMENTATION_SUMMARY.md` - Technical details
- `TEST_RESULTS.md` - Testing information

## Support

For issues:
1. Check `ROBOT_ARM_README.md` troubleshooting section
2. Verify wiring with `WIRING_DIAGRAM.md`
3. Run test suite: `python test_eye_tracking.py`

## Next Steps

After basic setup works:
1. Fine-tune sensitivity values
2. Adjust servo angle limits
3. Calibrate for your specific arm
4. Try advanced features (see ROBOT_ARM_README.md)

---

**Time to working system**: ~10 minutes
**Difficulty**: Beginner-friendly
**Cost**: $50-100 in parts
