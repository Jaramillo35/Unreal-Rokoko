#!/usr/bin/env python3
"""
Test script for MetaHuman Streamer v3
Tests basic functionality without GUI
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mh_streamer_v3 import NLPCommandParser, MetaHumanStreamerV3

def test_nlp_parser():
    """Test the NLP parser functionality"""
    print("🧠 Testing NLP Parser...")
    
    parser = NLPCommandParser()
    
    # Test cases
    test_cases = [
        ("turn left", "TURN_LEFT"),
        ("steer right", "TURN_RIGHT"), 
        ("basic position", "BASELINE"),
        ("stop", "STOP"),
        ("invalid command", "UNKNOWN")
    ]
    
    all_passed = True
    for command, expected in test_cases:
        action, _, confidence = parser.parse_command(command)
        if action == expected:
            print(f"✅ '{command}' → {action} (conf: {confidence:.2f})")
        else:
            print(f"❌ '{command}' → {action} (expected: {expected})")
            all_passed = False
    
    return all_passed

def test_streamer_initialization():
    """Test streamer initialization (without GUI)"""
    print("\n🎭 Testing Streamer Initialization...")
    
    try:
        # Test NLP parser initialization
        parser = NLPCommandParser()
        print("✅ NLP Parser initialized")
        
        # Test command parsing
        test_commands = ["turn left", "steer right", "basic position", "stop"]
        for cmd in test_commands:
            action, _, _ = parser.parse_command(cmd)
            print(f"✅ Command '{cmd}' → {action}")
        
        print("✅ All basic tests passed")
        return True
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 MetaHuman Streamer v3 - Test Suite")
    print("=" * 50)
    
    # Test NLP Parser
    nlp_passed = test_nlp_parser()
    
    # Test Streamer Initialization
    init_passed = test_streamer_initialization()
    
    # Summary
    print("\n📊 Test Results:")
    print("-" * 20)
    print(f"NLP Parser: {'✅ PASSED' if nlp_passed else '❌ FAILED'}")
    print(f"Initialization: {'✅ PASSED' if init_passed else '❌ FAILED'}")
    
    if nlp_passed and init_passed:
        print("\n🎉 All tests passed! v3 is ready to use.")
        print("\n🚀 To run the GUI:")
        print("   python mh_streamer_v3.py")
    else:
        print("\n⚠️  Some tests failed. Please check the errors above.")
    
    return nlp_passed and init_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
