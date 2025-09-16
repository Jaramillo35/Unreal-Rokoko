#!/usr/bin/env python3
"""
Explanation: What bones are targeted when clicking "Turn Left" in v2 streamer
Shows the exact OSC messages and bone movements for steering wheel turns
"""

def explain_turn_left_bones():
    """Explain which bones are targeted for left turn movements"""
    
    print("🎯 MetaHuman Streamer v2 - Turn Left Bone Targeting")
    print("=" * 60)
    
    print("\n🔄 WHEN YOU CLICK 'TURN LEFT':")
    print("-" * 40)
    print("The streamer switches from BASELINE mode to TURNING_LEFT mode")
    print("It loads the left turn ML model and generates a 60-frame sequence")
    print("Each frame contains data for ALL 37 bone channels simultaneously")
    print("The streamer sends 37 individual OSC messages per frame at 30 FPS")
    
    print("\n🦴 TARGETED BONES (37 total channels):")
    print("-" * 45)
    
    # Group bones by body region
    bone_groups = {
        "PELVIS (3 channels)": [
            "/bone/pelvis/pitch      (Pelvis_extension)",
            "/bone/pelvis/roll       (Pelvis_lateral_flexion_rotation)", 
            "/bone/pelvis/yaw        (Pelvis_axial_rotation)"
        ],
        
        "SPINE (15 channels - distributed across 5 spine bones)": [
            "/bone/spine_01/pitch    (Thorax_extension * 0.1)",
            "/bone/spine_02/pitch    (Thorax_extension * 0.2)",
            "/bone/spine_03/pitch    (Thorax_extension * 0.3)",
            "/bone/spine_04/pitch    (Thorax_extension * 0.25)",
            "/bone/spine_05/pitch    (Thorax_extension * 0.15)",
            "",
            "/bone/spine_01/roll     (Thorax_lateral_flexion_rotation * 0.1)",
            "/bone/spine_02/roll     (Thorax_lateral_flexion_rotation * 0.2)",
            "/bone/spine_03/roll     (Thorax_lateral_flexion_rotation * 0.3)",
            "/bone/spine_04/roll     (Thorax_lateral_flexion_rotation * 0.25)",
            "/bone/spine_05/roll     (Thorax_lateral_flexion_rotation * 0.15)",
            "",
            "/bone/spine_01/yaw      (Thorax_axial_rotation * 0.1)",
            "/bone/spine_02/yaw      (Thorax_axial_rotation * 0.2)",
            "/bone/spine_03/yaw      (Thorax_axial_rotation * 0.3)",
            "/bone/spine_04/yaw      (Thorax_axial_rotation * 0.25)",
            "/bone/spine_05/yaw      (Thorax_axial_rotation * 0.15)"
        ],
        
        "NECK (3 channels)": [
            "/bone/neck_01/pitch     (Neck_right_ward_rotation)",
            "/bone/neck_01/roll      (Neck_right_ward_rotation)",
            "/bone/neck_01/yaw       (Neck_right_ward_rotation)"
        ],
        
        "SHOULDERS (6 channels)": [
            "/bone/upperarm_r/pitch  (RightShoulder_flexion)",
            "/bone/upperarm_l/pitch  (LeftShoulder_flexion)",
            "/bone/upperarm_r/roll   (RightShoulder_abduction)",
            "/bone/upperarm_l/roll   (LeftShoulder_abduction)",
            "/bone/upperarm_r/yaw    (RightShoulder_external_rotation)",
            "/bone/upperarm_l/yaw    (LeftShoulder_external_rotation)"
        ],
        
        "FOREARMS (4 channels)": [
            "/bone/lowerarm_r/pitch  (RightForeArm_position_x * 0.5)",
            "/bone/lowerarm_l/pitch  (LeftForeArm_position_x * 0.5)",
            "/bone/lowerarm_r/roll   (RightForeArm_position_y * 0.5)",
            "/bone/lowerarm_l/roll   (LeftForeArm_position_y * 0.5)"
        ],
        
        "HANDS (6 channels)": [
            "/bone/hand_r/pitch      (RightWrist_flexion)",
            "/bone/hand_l/pitch      (LeftWrist_flexion)",
            "/bone/hand_r/roll       (RightWrist_adduction)",
            "/bone/hand_l/roll       (LeftWrist_adduction)",
            "/bone/hand_r/yaw        (RightWrist_pronation)",
            "/bone/hand_l/yaw        (LeftWrist_pronation)"
        ]
    }
    
    for group_name, bones in bone_groups.items():
        print(f"\n{group_name}:")
        for bone in bones:
            if bone:  # Skip empty strings
                print(f"  {bone}")
    
    print("\n🎯 KEY POINTS FOR TURN LEFT:")
    print("-" * 35)
    print("• ALL 37 bones receive data simultaneously")
    print("• Each bone gets 3 values: pitch, roll, yaw (except pelvis which has all 3)")
    print("• Spine movements are distributed across 5 spine bones with different weights")
    print("• The ML model generates realistic steering wheel turning motions")
    print("• Data flows: ML Model → Denormalization → OSC Transform → Unreal Engine")
    
    print("\n📊 DATA FLOW:")
    print("-" * 15)
    print("1. Click 'Turn Left' → Load left_turn_model")
    print("2. Generate 60-frame sequence (2 seconds at 30 FPS)")
    print("3. For each frame:")
    print("   - Denormalize data using baseline mean/std")
    print("   - Apply OSC transforms (scale, offset, clamp)")
    print("   - Send 37 individual OSC messages")
    print("   - Each message: /bone/{bone}/{axis} → float(degrees)")
    
    print("\n🔄 CONTINUOUS STREAMING:")
    print("-" * 25)
    print("• Streamer loops through the 60-frame sequence")
    print("• When sequence ends, it repeats from frame 0")
    print("• Click 'Return to Baseline' to stop turn and resume baseline")
    print("• Click 'Turn Right' to switch to right turn model")
    
    print("\n💡 WHY THESE BONES?")
    print("-" * 20)
    print("• PELVIS: Core body rotation for steering")
    print("• SPINE: Realistic torso twisting motion")
    print("• NECK: Head movement following body")
    print("• SHOULDERS: Arm positioning for steering wheel")
    print("• FOREARMS: Elbow and arm extension")
    print("• HANDS: Wrist and hand positioning on wheel")
    
    print("\n🎮 UNREAL ENGINE RECEPTION:")
    print("-" * 30)
    print("• Unreal receives 37 OSC messages per frame")
    print("• Each message updates one bone axis")
    print("• MetaHuman skeleton animates in real-time")
    print("• Smooth 30 FPS animation with realistic steering motion")

if __name__ == "__main__":
    explain_turn_left_bones()
