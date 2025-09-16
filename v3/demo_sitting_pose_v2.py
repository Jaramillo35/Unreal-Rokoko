#!/usr/bin/env python3
"""
Demo script for the updated sitting pose functionality in MetaHuman Streamer v3
Shows the exact OSC messages sent when triggering sitting pose
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mh_streamer_v3 import MetaHumanStreamerV3

def demo_sitting_pose():
    print("🪑 MetaHuman Streamer v3 - Updated Sitting Pose Demo")
    print("=" * 60)
    print()
    
    # Create streamer instance
    print("🔧 Initializing streamer...")
    app = MetaHumanStreamerV3()
    
    print(f"✅ Baseline sitting pose loaded: {len(app.baseline_sitting_pose)} values")
    print(f"📊 Column mapping: {len(app.COLUMN_TO_OSC)} bones mapped")
    print()
    
    # Test NLP patterns
    print("🧠 Testing NLP Parser for Sit Commands:")
    print("-" * 40)
    
    test_phrases = [
        "sit",
        "sit down", 
        "make it sit",
        "sitting position",
        "baseline sitting",
        "assume seated",
        "go to sitting"
    ]
    
    for phrase in test_phrases:
        action, original_text, confidence = app.nlp_parser.parse_command(phrase)
        status = "✅" if action == "POSE_SITTING" else "❌"
        print(f"  {status} '{phrase}' → {action} (conf: {confidence:.2f})")
    
    print()
    
    # Show OSC message structure
    print("📡 OSC Message Structure:")
    print("-" * 30)
    print("1. Pose Command (blending):")
    print("   Address: /cmd/pose")
    print("   Arguments: ['sitting', 0.35]")
    print()
    print("2. Per-bone messages (degrees):")
    print("   Format: /bone/{boneName}/{axis} <float degrees>")
    print()
    
    # Show sample messages
    print("🎯 Sample OSC Messages:")
    print("-" * 25)
    
    sample_count = 0
    for column_name, value in app.baseline_sitting_pose.items():
        if column_name in app.COLUMN_TO_OSC and sample_count < 10:
            bone_name, axis = app.COLUMN_TO_OSC[column_name]
            osc_address = f"/bone/{bone_name}/{axis}"
            print(f"   {osc_address} {float(value):.3f}")
            sample_count += 1
    
    if len(app.baseline_sitting_pose) > 10:
        print(f"   ... and {len(app.baseline_sitting_pose) - 10} more messages")
    
    print()
    
    # Show bone mapping stats
    mapped_columns = [col for col in app.baseline_sitting_pose.keys() if col in app.COLUMN_TO_OSC]
    unmapped_columns = [col for col in app.baseline_sitting_pose.keys() if col not in app.COLUMN_TO_OSC]
    
    print("📊 Mapping Statistics:")
    print("-" * 20)
    print(f"   Total columns: {len(app.baseline_sitting_pose)}")
    print(f"   Mapped to bones: {len(mapped_columns)}")
    print(f"   Unmapped: {len(unmapped_columns)}")
    
    if unmapped_columns:
        print(f"   Unmapped columns: {unmapped_columns[:5]}{'...' if len(unmapped_columns) > 5 else ''}")
    
    print()
    
    # Show GUI integration
    print("🖥️  GUI Integration:")
    print("-" * 18)
    print("• 'Sit' button added to quick actions")
    print("• Text input for natural language commands")
    print("• Enter key triggers NLP parsing")
    print("• Both button and text input call same handler")
    print()
    
    # Show data flow
    print("🔄 Complete Data Flow:")
    print("-" * 20)
    print("1. Load CSV: data/Baseline_SittingPose_Selected.csv")
    print("2. Compute mean per column → baseline pose dictionary")
    print("3. User types 'sit' or clicks 'Sit' button")
    print("4. NLP recognizes as POSE_SITTING action")
    print("5. Send /cmd/pose with 'sitting' + 0.35s blend")
    print("6. Send per-bone messages: /bone/{bone}/{axis}")
    print("7. Unreal Engine receives pose data")
    print()
    
    print("✅ UPDATED SITTING POSE READY!")
    print("The functionality now sends proper per-bone OSC messages")
    print("compatible with Unreal Engine's bone system.")

if __name__ == "__main__":
    demo_sitting_pose()
