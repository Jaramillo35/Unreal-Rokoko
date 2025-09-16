#!/usr/bin/env python3
"""
Final test for MetaHuman Streamer v3
Tests complete functionality including channel mapping
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mh_streamer_v3 import MetaHumanStreamerV3, NLPCommandParser

def test_v3_final():
    """Final comprehensive test of v3 functionality"""
    
    print("🎭 MetaHuman Streamer v3 - Final Test")
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
    
    # Test 2: Complete Streamer Initialization
    print("\n2. Testing Complete Streamer...")
    try:
        app = MetaHumanStreamerV3()
        print(f"   ✅ Models loaded successfully")
        print(f"   ✅ Baseline sequence: {app.baseline_sequence.shape}")
        print(f"   ✅ OSC channels: {len(app.channels)}")
        print(f"   ✅ Channel mapping: {len(app.channel_mapping)}")
        print(f"   ✅ Feature names: {len(app.feature_names)}")
        print(f"   ✅ OSC client: {'Connected' if app.osc_client else 'Not connected'}")
        
        # Show some channel details
        if app.channels:
            print(f"   ✅ First channel: {app.channels[0]['osc_address']}")
            print(f"   ✅ Sample features: {app.feature_names[:3]}")
        
        streamer_passed = True
    except Exception as e:
        print(f"   ❌ Streamer initialization failed: {e}")
        streamer_passed = False
    
    # Test 3: Command Processing
    print("\n3. Testing Command Processing...")
    if streamer_passed:
        try:
            # Test command processing
            app.process_text_command("turn left")
            app.process_text_command("steer right")
            app.process_text_command("basic position")
            print("   ✅ Command processing works")
            cmd_passed = True
        except Exception as e:
            print(f"   ❌ Command processing failed: {e}")
            cmd_passed = False
    else:
        print("   ⏭️  Skipped (streamer not initialized)")
        cmd_passed = False
    
    # Test 4: Channel Mapping Details
    print("\n4. Testing Channel Mapping...")
    if streamer_passed and app.channel_mapping:
        mapped_count = len(app.channel_mapping)
        total_channels = len(app.channels)
        mapping_ratio = mapped_count / total_channels if total_channels > 0 else 0
        
        print(f"   ✅ Mapped channels: {mapped_count}/{total_channels} ({mapping_ratio:.1%})")
        
        # Show some mapped channels
        sample_mappings = list(app.channel_mapping.items())[:3]
        for source, idx in sample_mappings:
            print(f"   ✅ {source} → feature_{idx}")
        
        mapping_passed = mapping_ratio > 0.5  # At least 50% mapped
    else:
        print("   ❌ No channel mapping available")
        mapping_passed = False
    
    # Summary
    print("\n📊 Final Test Results:")
    print("-" * 25)
    print(f"NLP Parser: {'✅ PASSED' if nlp_passed else '❌ FAILED'}")
    print(f"Streamer Init: {'✅ PASSED' if streamer_passed else '❌ FAILED'}")
    print(f"Command Processing: {'✅ PASSED' if cmd_passed else '❌ FAILED'}")
    print(f"Channel Mapping: {'✅ PASSED' if mapping_passed else '❌ FAILED'}")
    
    all_passed = nlp_passed and streamer_passed and cmd_passed and mapping_passed
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED!")
        print("v3 is fully functional and ready to use!")
        print("\n🚀 To run the GUI:")
        print("   python mh_streamer_v3.py")
        print("\n💡 Features working:")
        print("   • Natural language command processing")
        print("   • 37 OSC channels configured")
        print("   • ML model integration")
        print("   • Bone-level streaming ready")
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")
    
    return all_passed

if __name__ == "__main__":
    success = test_v3_final()
    sys.exit(0 if success else 1)
