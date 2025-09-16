# MetaHuman Streamer - How It Works

## 🎯 **Core Concept**

The streamer sends **individual OSC messages** to Unreal Engine, **one message per bone axis**. It does **NOT** send one big message with all information.

## 📡 **Message Structure**

### **Each OSC Message Contains:**
- **Address**: `/bone/{bone_name}/{axis}` (e.g., `/bone/hand_r/pitch`)
- **Value**: Single float in degrees (e.g., `15.5`)
- **Protocol**: UDP/OSC over network

### **Example of One Frame (37 messages):**
```
/bone/pelvis/pitch = 2.3°
/bone/pelvis/roll = -1.1°
/bone/pelvis/yaw = 0.8°
/bone/spine_01/pitch = 0.2°
/bone/spine_01/roll = 0.1°
/bone/spine_01/yaw = 0.3°
/bone/spine_02/pitch = 0.4°
/bone/spine_02/roll = 0.2°
/bone/spine_02/yaw = 0.6°
/bone/spine_03/pitch = 0.6°
/bone/spine_03/roll = 0.3°
/bone/spine_03/yaw = 0.9°
/bone/spine_04/pitch = 0.5°
/bone/spine_04/roll = 0.25°
/bone/spine_04/yaw = 0.75°
/bone/spine_05/pitch = 0.3°
/bone/spine_05/roll = 0.15°
/bone/spine_05/yaw = 0.45°
/bone/neck_01/pitch = 1.2°
/bone/neck_01/roll = -0.5°
/bone/neck_01/yaw = 0.7°
/bone/upperarm_r/pitch = 12.5°
/bone/upperarm_r/roll = 3.2°
/bone/upperarm_r/yaw = -2.1°
/bone/upperarm_l/pitch = -8.3°
/bone/upperarm_l/roll = -1.8°
/bone/upperarm_l/yaw = 1.5°
/bone/lowerarm_r/pitch = 5.2°
/bone/lowerarm_r/roll = 1.1°
/bone/lowerarm_l/pitch = -3.8°
/bone/lowerarm_l/roll = -0.9°
/bone/hand_r/pitch = 18.7°
/bone/hand_r/roll = 4.3°
/bone/hand_r/yaw = -6.2°
/bone/hand_l/pitch = -15.2°
/bone/hand_l/roll = -3.1°
/bone/hand_l/yaw = 5.8°
/mh/frame = 42
/mh/mode = "TURNING_LEFT"
```

## 🔄 **How It Works Step by Step**

### **1. Data Generation**
- Streamer loads **60-frame sequences** from trained models
- **Baseline**: Always streaming baseline position
- **Turn Left/Right**: Overlays turn movement on baseline

### **2. Per-Frame Processing**
For each frame (60 times per second):

1. **Get Frame Data**: Extract one frame from the 60-frame sequence
2. **Denormalize**: Convert from normalized values back to original units
3. **Send 37 Individual Messages**: One per bone axis
4. **Wait**: Sleep until next frame (16.67ms for 60 FPS)

### **3. Message Sending Loop**
```python
for channel in self.channels:  # 37 channels
    source_column = channel['source_column']      # e.g., "RightWrist_flexion"
    osc_address = channel['osc_address']          # e.g., "/bone/hand_r/pitch"
    transform = channel['transform']              # e.g., {"scale": 1.0, "offset": 0.0}
    
    # Get value from data
    raw_value = denormalized_data[feature_idx]
    
    # Apply transform
    transformed_value = transform['scale'] * raw_value + transform['offset']
    
    # Send individual OSC message
    self.osc_client.send_message(osc_address, float(transformed_value))
```

## 🎭 **Movement Modes**

### **Baseline Mode**
- Sends **baseline position** for all bones
- All 37 messages sent every frame
- MetaHuman stays in neutral sitting position

### **Turn Left Mode**
- Sends **baseline + left turn overlay**
- Same 37 messages, but values modified for left turn
- MetaHuman animates left turn movement

### **Turn Right Mode**
- Sends **baseline + right turn overlay**
- Same 37 messages, but values modified for right turn
- MetaHuman animates right turn movement

## 🦴 **Bone Distribution**

### **Spine Distribution (Special Case)**
Some features are distributed across multiple spine bones:

**Thorax_extension** → 5 spine bones:
- `/bone/spine_01/pitch` = 0.1 × thorax_value
- `/bone/spine_02/pitch` = 0.2 × thorax_value
- `/bone/spine_03/pitch` = 0.3 × thorax_value
- `/bone/spine_04/pitch` = 0.25 × thorax_value
- `/bone/spine_05/pitch` = 0.15 × thorax_value

This creates **realistic spine bending** instead of just one bone moving.

## ⚡ **Performance**

- **37 messages per frame**
- **60 frames per second**
- **2,220 messages per second total**
- **UDP protocol** (fast, no acknowledgment needed)
- **Local network** (127.0.0.1:7000)

## 🎮 **Unreal Engine Side**

Unreal Engine receives these messages and:
1. **Parses** the bone name and axis from the address
2. **Applies** the rotation to the corresponding bone
3. **Updates** the MetaHuman skeleton in real-time
4. **Renders** the animated character

## 🔧 **Why Individual Messages?**

1. **Unreal OSC Plugin**: Expects individual bone messages
2. **Real-time Performance**: No parsing of complex data structures
3. **Flexibility**: Easy to add/remove bones
4. **Debugging**: Can monitor individual bone values
5. **Standard Practice**: Common in motion capture systems

## 📊 **Data Flow Summary**

```
Raw Motion Data (CSV)
    ↓
Preprocessing (normalization, feature selection)
    ↓
GRU Models (generate 60-frame sequences)
    ↓
Streamer (extract frame, denormalize, transform)
    ↓
37 Individual OSC Messages per frame
    ↓
Unreal Engine (parse, apply to bones)
    ↓
MetaHuman Animation
```

The key point: **Each bone axis gets its own individual OSC message** - there's no single message containing all bone data!
