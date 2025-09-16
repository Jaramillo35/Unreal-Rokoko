#!/usr/bin/env python3
"""
Test script for port configuration in MetaHuman Streamer v2
"""

import tkinter as tk
from tkinter import ttk
import sys
import os

# Add the current directory to the path so we can import the streamer
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_port_configuration():
    """Test the port configuration functionality"""
    print("Testing port configuration...")
    
    try:
        # Import the streamer class
        from mh_streamer_v2 import MetaHumanStreamerV2
        
        # Create a test instance (this will create the GUI)
        print("Creating streamer instance...")
        app = MetaHumanStreamerV2()
        
        # Test initial values
        print(f"Initial host: {app.osc_host}")
        print(f"Initial port: {app.osc_port}")
        
        # Test updating values
        app.host_var.set("192.168.1.100")
        app.port_var.set("8080")
        
        print("Testing OSC client update...")
        app.update_osc_client()
        
        print(f"Updated host: {app.osc_host}")
        print(f"Updated port: {app.osc_port}")
        
        # Test invalid port
        print("Testing invalid port handling...")
        app.port_var.set("invalid")
        try:
            app.update_osc_client()
        except Exception as e:
            print(f"Expected error for invalid port: {e}")
        
        print("✓ Port configuration test completed successfully")
        return True
        
    except Exception as e:
        print(f"✗ Port configuration test failed: {e}")
        return False

def main():
    """Run the port configuration test"""
    print("=" * 50)
    print("MetaHuman Streamer v2 - Port Configuration Test")
    print("=" * 50)
    
    if test_port_configuration():
        print("🎉 Port configuration test passed!")
    else:
        print("⚠️  Port configuration test failed!")

if __name__ == "__main__":
    main()
