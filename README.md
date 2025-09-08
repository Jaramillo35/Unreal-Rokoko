# MetaHuman Steering Streamer GUI

A desktop GUI application for streaming OSC messages to Unreal Engine to drive MetaHuman characters using multi-channel steering data.

## Features

- **Real-time OSC Streaming**: Send multi-channel steering data to Unreal Engine at configurable FPS
- **Smooth Animations**: Cubic ease-in-out ramping for natural movement transitions
- **Multiple Actions**: Turn left, turn right, return to baseline, and heartbeat streaming
- **Configurable Parameters**: Adjustable IP, port, FPS, duration, and hold times
- **Channel Configuration**: Load custom channel mappings from JSON files
- **Hotkeys**: Keyboard shortcuts for quick access (Ctrl+S, Ctrl+R, Ctrl+L, Ctrl+B, Ctrl+X)
- **Settings Persistence**: Automatically saves and restores your settings
- **Real-time Logging**: Monitor streaming activity with timestamped logs
- **Connection Indicator**: Visual feedback showing OSC connection status and message statistics

## Installation

### Prerequisites
- Python 3.10 or higher
- Unreal Engine with MetaHuman setup
- OSC receiver configured in Unreal (listening on 127.0.0.1:8000 by default)

### Quick Start
```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python mh_streamer_gui.py
```

Or use the convenience script:
```bash
./install_and_run.sh
```

## Usage

### Basic Workflow
1. **Configure Connection**: Set IP address, port, and FPS in the Connection Settings
2. **Load Configuration**: Select your channel configuration JSON file (default provided)
3. **Start Streaming**: Click "Start Streaming" to begin sending heartbeat (zeros)
4. **Perform Actions**: Use "Turn Right", "Turn Left", or "Return to Baseline" buttons
5. **Stop When Done**: Click "Stop Streaming" to halt all OSC messages

### Keyboard Shortcuts
- `Ctrl+S`: Start Streaming
- `Ctrl+R`: Turn Right
- `Ctrl+L`: Turn Left
- `Ctrl+B`: Return to Baseline
- `Ctrl+X`: Stop Streaming

### Configuration File Format
The application uses JSON configuration files to define OSC channels and their steering amplitudes:

```json
{
  "meta": {
    "fps": 60,
    "default_duration": 1.5,
    "notes": "Steering features aligned to dataset column names"
  },
  "channels": [
    {
      "address": "/mh/RightWrist_flexion",
      "amp_right": 20.0,
      "amp_left": -15.0
    },
    {
      "address": "/mh/LeftWrist_flexion", 
      "amp_right": -12.0,
      "amp_left": 18.0
    }
  ]
}
```

### Parameters
- **IP Address**: Target IP for OSC messages (default: 127.0.0.1)
- **Port**: Target port for OSC messages (default: 8000)
- **FPS**: Streaming frame rate (default: 60)
- **Duration**: Ramp duration in seconds (default: 1.5)
- **Hold**: Hold time after ramp completion (default: 0.0)
- **Config File**: Path to channel configuration JSON

## Unreal Engine Setup

### OSC Receiver Setup
1. In Unreal Engine, add an OSC receiver component to your MetaHuman actor
2. Configure the receiver to listen on the same IP and port as the GUI
3. Map the OSC addresses to your MetaHuman control rig parameters

### Example Blueprint Setup
```blueprint
// In your MetaHuman Blueprint:
// 1. Add "OSC" plugin if not already enabled
// 2. Add "OSC Server" component
// 3. Set IP to 127.0.0.1, Port to 8000
// 4. Create event dispatchers for each OSC address
// 5. Connect to your MetaHuman control rig
```

## Testing

### Verification Steps
1. **Start App** → **Start Streaming** → Verify Unreal receives zeros for all `/mh/*` channels
2. **Turn Right** → Values should ramp to configured right amplitudes over duration
3. **Return to Baseline** → All values should ramp back to 0 over duration  
4. **Stop Streaming** → Should stop immediately and send zeros once
5. **Change Settings** → Modify IP/Port/FPS/Durations and re-test

### Connection Monitoring
The GUI includes a real-time connection indicator that shows:
- **Connection Status**: Visual indicator (●) with color coding:
  - 🔴 Red: Disconnected or connection failed
  - 🟢 Green: Connected and actively sending
  - 🟠 Orange: Connection timeout (no recent activity)
- **Message Statistics**: Live count of sent messages and errors
- **Automatic Timeout Detection**: Alerts if no OSC activity for 2+ seconds

### Debugging
- Check the connection indicator for real-time status
- Monitor the log console for detailed streaming information
- Verify OSC addresses match between GUI config and Unreal setup
- Use Unreal's PrintString nodes to verify OSC message reception
- Check network connectivity between GUI and Unreal
- Use the included `test_connection.py` script to test OSC reception

## File Structure

```
Unreal+Rokoko/
├── mh_streamer_gui.py          # Main application file
├── test_connection.py          # OSC receiver test script
├── requirements.txt            # Python dependencies
├── install_and_run.sh         # Convenience installation script
├── README.md                  # This documentation
└── data/processed/
    └── channels_steering_from_columns.json  # Default channel config
```

## Technical Details

### Architecture
- **GUI Thread**: Tkinter-based interface with real-time updates
- **Worker Thread**: Background OSC communication and animation processing
- **Thread-Safe Communication**: Queue-based command passing between threads
- **Smooth Animation**: Cubic ease-in-out envelope generation for natural movement

### OSC Message Format
- **Address**: `/mh/[ChannelName]` (e.g., `/mh/RightWrist_flexion`)
- **Value**: Float representing channel amplitude (degrees or normalized values)
- **Rate**: Configurable FPS (default 60)

### Animation System
- **Ramp Generation**: Cubic ease-in-out curves for smooth transitions
- **Multi-Channel Coordination**: All channels animate simultaneously
- **Hold Support**: Optional hold phase after ramp completion
- **Frame-Perfect Timing**: Precise frame timing using sleep-based scheduling

## Troubleshooting

### Common Issues
1. **No OSC Messages**: Check IP/port settings and Unreal OSC receiver setup
2. **Choppy Animation**: Increase FPS or check system performance
3. **Config Load Error**: Verify JSON file format and required keys
4. **GUI Freezing**: Check log console for worker thread errors

### Performance Tips
- Use appropriate FPS for your system (30-60 recommended)
- Close unnecessary applications during streaming
- Ensure stable network connection between GUI and Unreal
- Monitor log console for any error messages

## License

This project is provided as-is for educational and development purposes.
