#!/usr/bin/env python3
"""
Test script to verify OSC messages are being received
This will help debug why Unreal Engine might not be receiving data
"""

import time
from pythonosc import dispatcher, osc_server
import threading

# Global variables
received_messages = []
message_count = 0

def handle_mh_message(address, *args):
    """Handle incoming OSC messages from MetaHuman streamer"""
    global message_count
    message_count += 1
    
    received_messages.append({
        'address': address,
        'args': args,
        'timestamp': time.time()
    })
    
    # Print every 100th message to avoid spam
    if message_count % 100 == 0:
        print(f"[{message_count:04d}] {address}: {args}")

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

def main():
    """Main function"""
    print("MetaHuman Streamer v2 - OSC Reception Test")
    print("=" * 60)
    print("This script will listen for OSC messages from the streamer")
    print("Make sure to start the MetaHuman Streamer v2 and begin streaming!")
    print()
    
    # Start OSC server
    server = start_osc_server()
    
    try:
        print("Press Ctrl+C to stop...")
        server.serve_forever()
        
    except KeyboardInterrupt:
        print("\n\nStopping server...")
        server.shutdown()
        
        # Show statistics
        print("\n" + "=" * 60)
        print("RECEPTION STATISTICS")
        print("=" * 60)
        print(f"Total messages received: {len(received_messages)}")
        print(f"Message count: {message_count}")
        
        if received_messages:
            # Show unique addresses
            addresses = set(msg['address'] for msg in received_messages)
            print(f"Unique addresses: {len(addresses)}")
            
            # Show sample addresses
            print("\nSample addresses received:")
            for i, addr in enumerate(list(addresses)[:10]):
                print(f"  {i+1:2d}. {addr}")
            
            if len(addresses) > 10:
                print(f"  ... and {len(addresses) - 10} more addresses")
            
            # Show control messages
            control_msgs = [msg for msg in received_messages if msg['address'] in ['/mh/frame', '/mh/mode']]
            if control_msgs:
                print(f"\nControl messages received: {len(control_msgs)}")
                print("Latest control messages:")
                for msg in control_msgs[-5:]:
                    print(f"  {msg['address']}: {msg['args']}")
        else:
            print("\nNo messages received!")
            print("Possible issues:")
            print("1. Streamer not running")
            print("2. Wrong port (check streamer settings)")
            print("3. Firewall blocking UDP traffic")
            print("4. OSC client not sending to correct address")
        
        print("\n" + "=" * 60)
        print("TEST COMPLETE")
        print("=" * 60)

if __name__ == "__main__":
    main()
