#!/usr/bin/env python3
"""
Demo script to show what information the MetaHuman Streamer v2 is sending
This script will capture and display the OSC messages being sent
"""

import numpy as np
import json
import time
from pythonosc import dispatcher, osc_server
import threading
import sys
import os

# Add the current directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Global variables to store received messages
received_messages = []
message_count = 0

def handle_mh_message(address, *args):
    """Handle incoming OSC messages from MetaHuman streamer"""
    global message_count
    message_count += 1
    
    # Store the message
    received_messages.append({
        'address': address,
        'args': args,
        'timestamp': time.time()
    })
    
    # Print the message
    print(f"[{message_count:03d}] {address}: {args}")

def start_osc_server(host="127.0.0.1", port=7000):
    """Start OSC server to receive messages"""
    disp = dispatcher.Dispatcher()
    
    # Register handler for all MetaHuman messages
    disp.map("/mh/*", handle_mh_message)
    
    server = osc_server.ThreadingOSCServer((host, port), disp)
    print(f"OSC Server started on {host}:{port}")
    print("Waiting for MetaHuman Streamer v2 messages...")
    print("=" * 60)
    
    return server

def analyze_messages():
    """Analyze the received messages and show statistics"""
    if not received_messages:
        print("No messages received yet.")
        return
    
    print("\n" + "=" * 60)
    print("MESSAGE ANALYSIS")
    print("=" * 60)
    
    # Group messages by address
    address_counts = {}
    for msg in received_messages:
        addr = msg['address']
        address_counts[addr] = address_counts.get(addr, 0) + 1
    
    print(f"Total messages received: {len(received_messages)}")
    print(f"Unique addresses: {len(address_counts)}")
    print("\nMessage frequency by address:")
    
    # Sort by frequency
    sorted_addresses = sorted(address_counts.items(), key=lambda x: x[1], reverse=True)
    for addr, count in sorted_addresses[:10]:  # Show top 10
        print(f"  {addr}: {count} messages")
    
    if len(sorted_addresses) > 10:
        print(f"  ... and {len(sorted_addresses) - 10} more addresses")
    
    # Show sample data for different types of messages
    print("\nSample data types:")
    
    # Find position messages
    position_msgs = [msg for msg in received_messages if 'position' in msg['address']]
    if position_msgs:
        print(f"\nPosition data example ({position_msgs[0]['address']}):")
        print(f"  Value: {position_msgs[0]['args'][0]}")
    
    # Find rotation messages
    rotation_msgs = [msg for msg in received_messages if any(rot in msg['address'] for rot in ['flexion', 'rotation', 'tilt'])]
    if rotation_msgs:
        print(f"\nRotation data example ({rotation_msgs[0]['address']}):")
        print(f"  Value: {rotation_msgs[0]['args'][0]}")
    
    # Find frame info
    frame_msgs = [msg for msg in received_messages if msg['address'] == '/mh/frame']
    if frame_msgs:
        print(f"\nFrame info:")
        print(f"  Current frame: {frame_msgs[-1]['args'][0]}")
    
    mode_msgs = [msg for msg in received_messages if msg['address'] == '/mh/mode']
    if mode_msgs:
        print(f"  Current mode: {mode_msgs[-1]['args'][0]}")

def show_data_structure():
    """Show the structure of data being sent"""
    print("\n" + "=" * 60)
    print("DATA STRUCTURE OVERVIEW")
    print("=" * 60)
    
    try:
        # Load normalization parameters to understand the data
        with open("data/processed_v2/normalization_params.json", 'r') as f:
            norm_params = json.load(f)
        
        feature_columns = norm_params['feature_columns']
        
        print(f"Total features being streamed: {len(feature_columns)}")
        print(f"Target frames per sequence: {norm_params['target_frames']}")
        
        print("\nFeature categories:")
        categories = {}
        for col in feature_columns:
            # Extract category from column name
            if 'position' in col:
                category = 'Position'
            elif 'velocity' in col:
                category = 'Velocity'
            elif 'acceleration' in col:
                category = 'Acceleration'
            elif any(rot in col for rot in ['flexion', 'rotation', 'tilt']):
                category = 'Rotation'
            else:
                category = 'Other'
            
            categories[category] = categories.get(category, 0) + 1
        
        for cat, count in categories.items():
            print(f"  {cat}: {count} features")
        
        print("\nBody parts being tracked:")
        body_parts = set()
        for col in feature_columns:
            if 'Pelvis' in col:
                body_parts.add('Pelvis')
            elif 'Chest' in col or 'Thorax' in col:
                body_parts.add('Chest/Thorax')
            elif 'Head' in col or 'Neck' in col:
                body_parts.add('Head/Neck')
            elif 'Shoulder' in col or 'Scapula' in col or 'UpperArm' in col:
                body_parts.add('Shoulder/Arm')
            elif 'ForeArm' in col or 'Wrist' in col or 'Hand' in col:
                body_parts.add('Forearm/Hand')
            elif 'Digit' in col:
                body_parts.add('Fingers')
        
        for part in sorted(body_parts):
            print(f"  {part}")
        
        print(f"\nSample feature names:")
        for i, col in enumerate(feature_columns[:10]):
            print(f"  {i+1:2d}. {col}")
        if len(feature_columns) > 10:
            print(f"  ... and {len(feature_columns) - 10} more features")
            
    except Exception as e:
        print(f"Could not load feature information: {e}")

def main():
    """Main function to demonstrate OSC output"""
    print("MetaHuman Streamer v2 - OSC Output Demo")
    print("=" * 60)
    print("This script will show you exactly what data the streamer sends")
    print("Make sure to start the MetaHuman Streamer v2 in another terminal")
    print("and begin streaming to see the data!")
    print()
    
    # Show data structure first
    show_data_structure()
    
    # Start OSC server
    server = start_osc_server()
    
    try:
        # Run server for 30 seconds or until interrupted
        print("\nPress Ctrl+C to stop and analyze messages...")
        server.serve_forever()
        
    except KeyboardInterrupt:
        print("\n\nStopping server...")
        server.shutdown()
        
        # Analyze received messages
        analyze_messages()
        
        print("\n" + "=" * 60)
        print("DEMO COMPLETE")
        print("=" * 60)
        print("To see live data:")
        print("1. Run: python mh_streamer_v2.py")
        print("2. Configure OSC settings if needed")
        print("3. Click 'Start Streaming'")
        print("4. Run this demo script again")

if __name__ == "__main__":
    main()
