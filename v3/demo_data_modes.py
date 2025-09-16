#!/usr/bin/env python3
"""
Demo: MetaHuman Streamer v3 - Data Modes
Shows the difference between Real and Mock data modes
"""

import sys
import os
import time
import math
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mh_streamer_v3 import MetaHumanStreamerV3

def demo_data_modes():
    """Demonstrate the two data modes"""
    
    print("🎭 MetaHuman Streamer v3 - Data Modes Demo")
    print("=" * 60)
    
    print("\n🎯 NEW FEATURES ADDED:")
    print("-" * 25)
    print("• Two data mode buttons in GUI")
    print("• Real Data: Uses ML models (37 channels)")
    print("• Mock Data: Only 2 signals (LeftForeArm_roll, RightForeArm_roll)")
    print("• Easy switching between modes while streaming")
    
    print("\n📊 DATA MODE COMPARISON:")
    print("-" * 30)
    
    print("\n🔄 REAL DATA MODE:")
    print("  • Uses trained ML models")
    print("  • 37 bone channels streamed")
    print("  • Realistic steering movements")
    print("  • Same as v2 functionality")
    print("  • Commands: 'turn left', 'turn right', 'basic position'")
    
    print("\n🎮 MOCK DATA MODE:")
    print("  • Only 2 signals: LeftForeArm_roll, RightForeArm_roll")
    print("  • Animated sine wave values")
    print("  • Perfect for testing OSC connection")
    print("  • Easy to verify in Unreal Engine")
    print("  • Values range: -50° to +50°")
    
    print("\n🎯 MOCK DATA BEHAVIOR:")
    print("-" * 25)
    
    print("\nBASELINE (basic position):")
    print("  • LeftForeArm_roll:  -5° to +5° (slow sine wave)")
    print("  • RightForeArm_roll: -5° to +5° (slow cosine wave)")
    
    print("\nTURN LEFT:")
    print("  • LeftForeArm_roll:  +10° to +50° (upward movement)")
    print("  • RightForeArm_roll: -50° to -10° (downward movement)")
    
    print("\nTURN RIGHT:")
    print("  • LeftForeArm_roll:  -50° to -10° (downward movement)")
    print("  • RightForeArm_roll: +10° to +50° (upward movement)")
    
    print("\n🔧 OSC MESSAGES SENT:")
    print("-" * 25)
    print("Real Mode:")
    print("  • 37 messages per frame")
    print("  • /bone/pelvis/pitch, /bone/spine_01/yaw, etc.")
    print("  • Complex ML-generated values")
    
    print("\nMock Mode:")
    print("  • 2 messages per frame")
    print("  • /bone/lowerarm_l/roll (LeftForeArm_roll)")
    print("  • /bone/lowerarm_r/roll (RightForeArm_roll)")
    print("  • Simple animated values")
    
    print("\n🚀 HOW TO USE:")
    print("-" * 15)
    print("1. Run: python mh_streamer_v3.py")
    print("2. Click 'Start Streaming'")
    print("3. Choose data mode:")
    print("   • Click 'Real Data (ML Models)' for full functionality")
    print("   • Click 'Mock Data (2 Signals)' for simple testing")
    print("4. Type commands: 'turn left', 'turn right', 'basic position'")
    print("5. Watch the log console for data values")
    
    print("\n💡 TESTING RECOMMENDATIONS:")
    print("-" * 30)
    print("• Start with Mock Data mode to verify OSC connection")
    print("• Monitor /bone/lowerarm_l/roll and /bone/lowerarm_r/roll")
    print("• Switch to Real Data mode for full MetaHuman animation")
    print("• Use 'basic position' to return to neutral")
    
    print("\n🎮 GUI LAYOUT:")
    print("-" * 15)
    print("┌─ Controls ─────────────────────────┐")
    print("│ [Start Streaming]                  │")
    print("│ [Turn Left] [Turn Right] [Basic]   │")
    print("│ Data Mode: [Real Data] [Mock Data] │")
    print("│ Mode: REAL (ML Models)             │")
    print("└────────────────────────────────────┘")
    
    print("\n✅ READY TO TEST!")
    print("The v3 streamer now has both Real and Mock data modes")
    print("Perfect for proof of concept and OSC connection testing!")

if __name__ == "__main__":
    demo_data_modes()
