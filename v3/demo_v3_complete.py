#!/usr/bin/env python3
"""
Complete Demo: MetaHuman Streamer v3
Shows the full workflow from text commands to bone-level streaming
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mh_streamer_v3 import NLPCommandParser

def demo_v3_workflow():
    """Demonstrate the complete v3 workflow"""
    
    print("🎭 MetaHuman Streamer v3 - Complete Demo")
    print("=" * 60)
    
    print("\n🎯 V3 FEATURES:")
    print("-" * 20)
    print("• Natural Language Processing for commands")
    print("• Same 37 bone channels as v2")
    print("• ML model integration for realistic movements")
    print("• Text input: 'turn left', 'steer right', 'basic position'")
    print("• Real-time command processing and execution")
    
    print("\n🧠 NLP COMMAND PARSER:")
    print("-" * 25)
    
    # Initialize parser
    parser = NLPCommandParser()
    
    # Demo commands
    demo_commands = [
        "turn left",
        "steer right", 
        "basic position",
        "return to baseline",
        "stop",
        "go left",
        "right turn",
        "neutral position"
    ]
    
    print("Testing various command inputs:")
    for i, cmd in enumerate(demo_commands, 1):
        action, original, confidence = parser.parse_command(cmd)
        status = "✅" if action != "UNKNOWN" else "❌"
        print(f"{i}. '{cmd:<20}' → {status} {action} (conf: {confidence:.2f})")
    
    print("\n🦴 BONE TARGETING (Same as v2):")
    print("-" * 35)
    print("When you type 'turn left' or 'steer right':")
    print("• 37 bone channels receive data simultaneously")
    print("• Pelvis, Spine (5 bones), Neck, Shoulders, Forearms, Hands")
    print("• Each bone gets pitch, roll, yaw values")
    print("• ML model generates realistic steering motion")
    
    print("\n📊 DATA FLOW:")
    print("-" * 15)
    print("1. User types: 'turn left'")
    print("2. NLP Parser: Recognizes as TURN_LEFT action")
    print("3. Streamer: Switches to left turn mode")
    print("4. ML Model: Loads left_turn_gru.pth")
    print("5. Sequence: Generates 60-frame animation")
    print("6. OSC Streaming: Sends 37 messages per frame")
    print("7. Unreal Engine: Animates MetaHuman skeleton")
    
    print("\n🎮 GUI INTERFACE:")
    print("-" * 20)
    print("• Text Input Field: Type natural language commands")
    print("• Send Command Button: Process the input")
    print("• Quick Action Buttons: One-click common commands")
    print("• Log Console: See commands and OSC messages")
    print("• OSC Settings: Configure host and port")
    print("• Start/Stop Streaming: Control the streamer")
    
    print("\n🔄 COMMAND EXAMPLES:")
    print("-" * 22)
    
    examples = {
        "Turn Left": [
            "turn left",
            "steer left", 
            "go left",
            "left turn",
            "turn to the left"
        ],
        "Turn Right": [
            "turn right",
            "steer right",
            "go right", 
            "right turn",
            "turn to the right"
        ],
        "Basic Position": [
            "basic position",
            "return to baseline",
            "default position",
            "center position",
            "straighten up",
            "neutral"
        ],
        "Stop": [
            "stop",
            "halt",
            "pause",
            "stop turning"
        ]
    }
    
    for category, commands in examples.items():
        print(f"\n{category}:")
        for cmd in commands:
            action, _, _ = parser.parse_command(cmd)
            print(f"  • '{cmd}' → {action}")
    
    print("\n🚀 USAGE INSTRUCTIONS:")
    print("-" * 25)
    print("1. Run: python mh_streamer_v3.py")
    print("2. Click 'Start Streaming'")
    print("3. Type commands in the text input field")
    print("4. Press Enter or click 'Send Command'")
    print("5. Watch the MetaHuman animate in Unreal Engine")
    print("6. Use 'basic position' to return to baseline")
    
    print("\n💡 KEY ADVANTAGES OVER V2:")
    print("-" * 30)
    print("• Natural language input instead of button clicks")
    print("• More intuitive and flexible command system")
    print("• Same powerful bone-level streaming capabilities")
    print("• Easy to extend with new commands")
    print("• Better user experience for complex workflows")
    
    print("\n🎯 TARGET BONES (37 channels):")
    print("-" * 30)
    bone_groups = {
        "Pelvis": 3,
        "Spine (5 bones)": 15, 
        "Neck": 3,
        "Shoulders": 6,
        "Forearms": 4,
        "Hands": 6
    }
    
    total = 0
    for group, count in bone_groups.items():
        print(f"• {group}: {count} channels")
        total += count
    
    print(f"• Total: {total} bone channels")
    
    print("\n🎉 V3 IS READY TO USE!")
    print("-" * 25)
    print("The streamer combines the power of v2's bone-level")
    print("streaming with intuitive natural language commands.")
    print("Perfect for interactive MetaHuman control!")

if __name__ == "__main__":
    demo_v3_workflow()
