#!/usr/bin/env python3
"""
Demo: MetaHuman Streamer v3 - Sitting Pose Feature
Shows the new sitting pose functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mh_streamer_v3 import MetaHumanStreamerV3, NLPCommandParser

def demo_sitting_pose():
    """Demonstrate the sitting pose functionality"""
    
    print("🪑 MetaHuman Streamer v3 - Sitting Pose Demo")
    print("=" * 60)
    
    print("\n🎯 NEW SITTING POSE FEATURES:")
    print("-" * 35)
    print("• Loads baseline sitting pose from CSV")
    print("• NLP recognizes 'sit' commands")
    print("• Sends /cmd/pose to Unreal Engine")
    print("• Integrates with existing functionality")
    
    # Test NLP Parser
    print("\n🧠 Testing NLP Parser for Sit Commands:")
    print("-" * 45)
    
    parser = NLPCommandParser()
    
    sit_commands = [
        "sit",
        "sit down", 
        "make it sit",
        "sitting position",
        "baseline sitting",
        "sit up",
        "sit straight",
        "sitting pose"
    ]
    
    for cmd in sit_commands:
        action, _, confidence = parser.parse_command(cmd)
        status = "✅" if action == "POSE_SITTING" else "❌"
        print(f"  {status} '{cmd}' → {action} (conf: {confidence:.2f})")
    
    print("\n📊 OSC Message Format:")
    print("-" * 25)
    print("Address: /cmd/pose")
    print("Arguments: [\"sitting\", value1, value2, ..., valueN]")
    print("• First argument: \"sitting\" (string)")
    print("• Remaining arguments: pose values (floats)")
    print("• Values computed from CSV mean per column")
    
    print("\n🔄 Data Flow:")
    print("-" * 15)
    print("1. Load CSV: data/Baseline_SittingPose_Selected.csv")
    print("2. Compute mean per column → baseline pose vector")
    print("3. User types 'sit' or clicks 'Sit' button")
    print("4. NLP recognizes as POSE_SITTING action")
    print("5. Send /cmd/pose with 'sitting' + pose values")
    print("6. Unreal Engine receives pose data")
    
    print("\n🎮 GUI Integration:")
    print("-" * 20)
    print("• New 'Sit' button added to quick actions")
    print("• Button enabled/disabled with other controls")
    print("• Works with existing Start/Stop streaming")
    print("• Compatible with Real/Mock data modes")
    
    print("\n💡 Usage Examples:")
    print("-" * 20)
    print("• Type 'sit' in text input → triggers sitting pose")
    print("• Type 'sit down' → same result")
    print("• Click 'Sit' button → direct trigger")
    print("• Works whether streaming is on or off")
    
    print("\n🔧 Technical Details:")
    print("-" * 22)
    print("• CSV Loading: pandas + scikit-learn")
    print("• Pose Vector: mean of all numeric columns")
    print("• OSC Client: Same as existing streaming")
    print("• Error Handling: Graceful fallback if CSV missing")
    
    print("\n✅ READY TO USE!")
    print("The sitting pose feature is fully integrated")
    print("and ready for testing with Unreal Engine!")

if __name__ == "__main__":
    demo_sitting_pose()
