#!/usr/bin/env python3
"""
Demonstration of how the streamer sends individual OSC messages to Unreal Engine
"""

import json
import numpy as np

def demonstrate_message_structure():
    """Show exactly how messages are structured and sent"""
    
    print("🎭 MetaHuman Streamer - Message Structure Demo")
    print("=" * 60)
    
    # Load OSC configuration
    with open('v2/osc_channels_config.json', 'r') as f:
        config = json.load(f)
    
    print(f"📡 OSC Configuration:")
    print(f"   Host: {config['meta']['osc']['host']}")
    print(f"   Port: {config['meta']['osc']['port']}")
    print(f"   Rate: {config['meta']['rate_hz']} Hz")
    print(f"   Units: {config['meta']['units']}")
    print()
    
    print("🔄 How Messages Are Sent:")
    print("-" * 30)
    print("The streamer sends INDIVIDUAL OSC messages, one per bone axis.")
    print("It does NOT send one big message with all data.")
    print()
    
    # Simulate some sample data
    np.random.seed(42)  # For reproducible demo
    sample_data = np.random.normal(0, 1, 864)  # Simulated normalized data
    
    print("📤 Example: One Frame (37 Individual Messages)")
    print("=" * 50)
    
    frame_count = 1
    mode = "TURNING_LEFT"
    
    # Simulate sending messages
    message_count = 0
    for i, channel in enumerate(config['channels']):
        source_column = channel['source_column']
        osc_address = channel['osc_address']
        transform = channel['transform']
        
        # Simulate getting value from data
        raw_value = sample_data[i % len(sample_data)]
        
        # Apply transform
        transformed_value = transform['scale'] * raw_value + transform['offset']
        
        # Format the message
        message_count += 1
        print(f"{message_count:2d}. {osc_address:25s} = {transformed_value:8.3f}°")
        
        # Show first 10 messages in detail
        if message_count <= 10:
            print(f"    └─ Source: {source_column}")
            print(f"    └─ Transform: scale={transform['scale']}, offset={transform['offset']}")
            print()
    
    print("...")
    print(f"    ... and {len(config['channels']) - 10} more messages")
    print()
    
    # Show control messages
    print("🎮 Control Messages:")
    print(f"    /mh/frame = {frame_count}")
    print(f"    /mh/mode = \"{mode}\"")
    print()
    
    print("📊 Message Statistics:")
    print(f"    Total messages per frame: {len(config['channels']) + 2}")
    print(f"    Messages per second: {(len(config['channels']) + 2) * 60}")
    print(f"    Protocol: UDP/OSC")
    print(f"    Network: Local (127.0.0.1:7000)")
    print()
    
    print("🦴 Bone Distribution:")
    print("-" * 20)
    bone_counts = {}
    for channel in config['channels']:
        bone = channel['osc_address'].split('/')[2]
        if bone not in bone_counts:
            bone_counts[bone] = 0
        bone_counts[bone] += 1
    
    for bone, count in sorted(bone_counts.items()):
        print(f"    {bone:15s}: {count:2d} messages")
    print()
    
    print("🎯 Key Points:")
    print("    ✅ Each bone axis gets its own OSC message")
    print("    ✅ 37 individual messages per frame (not 1 big message)")
    print("    ✅ Messages sent 60 times per second")
    print("    ✅ Unreal Engine receives and processes each message individually")
    print("    ✅ This creates smooth, real-time animation")

if __name__ == "__main__":
    demonstrate_message_structure()
