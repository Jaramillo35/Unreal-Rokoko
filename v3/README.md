# MetaHuman Streamer v3 - NLP + Bone Streaming

## 🎯 Overview

MetaHuman Streamer v3 combines **Natural Language Processing** with **bone-level streaming** to create an intuitive interface for controlling MetaHuman animations in Unreal Engine. Users can type natural commands like "turn left" or "steer right" and the streamer will automatically trigger the appropriate bone-level animations.

## 🚀 Key Features

- **Natural Language Processing**: Understands text commands like "turn left", "steer right", "basic position"
- **Bone-Level Streaming**: Same 37-channel bone streaming as v2 for realistic animations
- **ML Model Integration**: Uses trained GRU models for realistic steering movements
- **Real-Time Processing**: Instant command recognition and execution
- **Multiple Command Variations**: Supports various ways to express the same command
- **GUI Interface**: Clean, intuitive interface with text input and quick action buttons

## 🎮 Supported Commands

### Turn Left
- `turn left`
- `steer left`
- `go left`
- `left turn`
- `turn to the left`

### Turn Right
- `turn right`
- `steer right`
- `go right`
- `right turn`
- `turn to the right`

### Basic Position (Return to Baseline)
- `basic position`
- `return to baseline`
- `default position`
- `normal position`
- `center position`
- `straighten up`
- `baseline`
- `neutral`

### Stop
- `stop`
- `halt`
- `pause`
- `stop turning`
- `end`

## 🦴 Bone Targeting

When you input a command, v3 targets the **same 37 bone channels** as v2:

### Body Regions (37 total channels):
- **Pelvis** (3 channels): pitch, roll, yaw
- **Spine** (15 channels): 5 spine bones × 3 axes each
- **Neck** (3 channels): pitch, roll, yaw
- **Shoulders** (6 channels): left/right upper arms × 3 axes
- **Forearms** (4 channels): left/right lower arms × 2 axes
- **Hands** (6 channels): left/right hands × 3 axes

## 🛠️ Installation & Setup

### Prerequisites
- Python 3.8+
- PyTorch
- python-osc
- tkinter (usually included with Python)

### Dependencies
```bash
pip install torch python-osc numpy
```

### Required Data Files
- `data/processed_v2/` directory with:
  - `baseline_gru.pth` - Baseline movement model
  - `left_turn_gru.pth` - Left turn movement model
  - `right_turn_gru.pth` - Right turn movement model
  - `baseline_data.npy` - Baseline sequence data
  - `left_turn_data.npy` - Left turn sequence data
  - `right_turn_data.npy` - Right turn sequence data
  - `normalization_params.json` - Data normalization parameters
- `v2/osc_channels_config.json` - OSC channel configuration

## 🚀 Usage

### Running the Streamer
```bash
cd v3
python mh_streamer_v3.py
```

### GUI Interface
1. **Start Streaming**: Click "Start Streaming" to begin
2. **Text Input**: Type commands in the text input field
3. **Send Command**: Press Enter or click "Send Command"
4. **Quick Actions**: Use the quick action buttons for common commands
5. **OSC Settings**: Configure host and port for Unreal Engine

### Example Workflow
1. Start the streamer
2. Click "Start Streaming"
3. Type "turn left" and press Enter
4. MetaHuman animates left turn using 37 bone channels
5. Type "basic position" to return to baseline
6. Type "turn right" for right turn animation

## 🔧 Configuration

### OSC Settings
- **Default Host**: 127.0.0.1
- **Default Port**: 7000
- **Rate**: 30 FPS
- **Format**: `/bone/{bone}/{axis}` → float(degrees)

### Turn Duration
- Configurable turn duration (default: 2.0 seconds)
- 60-frame sequences at 30 FPS

## 📊 Data Flow

```
Text Command → NLP Parser → Action Recognition → 
ML Model Selection → Bone Sequence Generation → 
OSC Message Streaming → Unreal Engine Animation
```

## 🎯 Technical Details

### NLP Parser
- **Regex-based**: Fast, deterministic pattern matching
- **Case-insensitive**: Works with any capitalization
- **Synonym support**: Multiple ways to express same command
- **Confidence scoring**: Binary matching with confidence values

### Bone Streaming
- **37 channels**: Complete upper body animation
- **Real-time**: 30 FPS continuous streaming
- **ML-driven**: Realistic movements from trained models
- **Smooth transitions**: Seamless switching between modes

### GUI Features
- **Real-time logging**: See commands and OSC messages
- **Statistics**: Track message count and errors
- **Data display**: Toggle detailed data values
- **Quick actions**: One-click common commands

## 🔄 Comparison with v2

| Feature | v2 | v3 |
|---------|----|----|
| **Interface** | Button clicks | Text input + buttons |
| **Commands** | Fixed buttons | Natural language |
| **Bone Streaming** | ✅ 37 channels | ✅ 37 channels |
| **ML Models** | ✅ GRU models | ✅ GRU models |
| **OSC Format** | `/bone/{bone}/{axis}` | `/bone/{bone}/{axis}` |
| **Flexibility** | Limited | High (NLP) |

## 🐛 Troubleshooting

### Common Issues
1. **"Models not loaded"**: Check data files in `data/processed_v2/`
2. **"OSC client not initialized"**: Verify host/port settings
3. **"Unknown command"**: Check command spelling and format
4. **"No channels configured"**: Verify `v2/osc_channels_config.json`

### Debug Mode
- Enable "Show data values" in log console
- Check log for detailed OSC message information
- Verify Unreal Engine OSC reception

## 🎮 Unreal Engine Integration

### OSC Reception
- **Address Pattern**: `/bone/{bone}/{axis}`
- **Payload**: Single float (degrees)
- **Rate**: 30 FPS
- **Control Messages**: `/mh/frame`, `/mh/mode`

### MetaHuman Setup
- Configure MetaHuman to receive OSC messages
- Map bone addresses to MetaHuman skeleton
- Set up real-time animation blending

## 📈 Future Enhancements

- **More Commands**: Add head movements, gestures, etc.
- **Voice Input**: Speech-to-text integration
- **Custom Commands**: User-defined command patterns
- **Animation Blending**: Smooth transitions between movements
- **Performance Metrics**: Detailed animation statistics

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add new command patterns to `NLPCommandParser`
4. Test with various input variations
5. Submit a pull request

## 📄 License

Same as the main project license.

---

**MetaHuman Streamer v3** - Natural Language Processing meets Bone-Level Animation Control
