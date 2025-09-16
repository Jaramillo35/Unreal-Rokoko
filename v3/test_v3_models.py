#!/usr/bin/env python3
"""
Test v3 streamer model loading and basic functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mh_streamer_v3 import MetaHumanStreamerV3, NLPCommandParser

def test_v3_complete():
    """Test complete v3 functionality"""
    
    print("🧪 MetaHuman Streamer v3 - Complete Test")
    print("=" * 50)
    
    # Test 1: NLP Parser
    print("\n1. Testing NLP Parser...")
    parser = NLPCommandParser()
    
    test_commands = [
        ("turn left", "TURN_LEFT"),
        ("steer right", "TURN_RIGHT"),
        ("basic position", "BASELINE"),
        ("stop", "STOP")
    ]
    
    nlp_passed = True
    for cmd, expected in test_commands:
        action, _, _ = parser.parse_command(cmd)
        if action == expected:
            print(f"   ✅ '{cmd}' → {action}")
        else:
            print(f"   ❌ '{cmd}' → {action} (expected {expected})")
            nlp_passed = False
    
    # Test 2: Model Loading
    print("\n2. Testing Model Loading...")
    try:
        app = MetaHumanStreamerV3()
        print("   ✅ Models loaded successfully")
        print(f"   ✅ Baseline sequence: {app.baseline_sequence.shape}")
        print(f"   ✅ Channels configured: {len(app.channels)}")
        print(f"   ✅ Feature names: {len(app.feature_names)}")
        model_passed = True
    except Exception as e:
        print(f"   ❌ Model loading failed: {e}")
        model_passed = False
    
    # Test 3: Command Processing
    print("\n3. Testing Command Processing...")
    if model_passed:
        try:
            # Test command processing (without GUI)
            app.process_text_command("turn left")
            app.process_text_command("steer right")
            app.process_text_command("basic position")
            print("   ✅ Command processing works")
            cmd_passed = True
        except Exception as e:
            print(f"   ❌ Command processing failed: {e}")
            cmd_passed = False
    else:
        print("   ⏭️  Skipped (models not loaded)")
        cmd_passed = False
    
    # Summary
    print("\n📊 Test Results:")
    print("-" * 20)
    print(f"NLP Parser: {'✅ PASSED' if nlp_passed else '❌ FAILED'}")
    print(f"Model Loading: {'✅ PASSED' if model_passed else '❌ FAILED'}")
    print(f"Command Processing: {'✅ PASSED' if cmd_passed else '❌ FAILED'}")
    
    all_passed = nlp_passed and model_passed and cmd_passed
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED!")
        print("v3 is ready to use with GUI:")
        print("   python mh_streamer_v3.py")
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")
    
    return all_passed

if __name__ == "__main__":
    success = test_v3_complete()
    sys.exit(0 if success else 1)
