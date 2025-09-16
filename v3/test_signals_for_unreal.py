#!/usr/bin/env python3
"""
Test Signals for Unreal Engine
Analyzes which OSC signals change the most during steering movements
"""

import sys
import os
import numpy as np
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mh_streamer_v3 import MetaHumanStreamerV3

def analyze_signal_variations():
    """Analyze which signals change the most during steering movements"""
    
    print("🎯 MetaHuman Streamer v3 - Signal Analysis for Unreal Testing")
    print("=" * 70)
    
    try:
        # Load the streamer
        app = MetaHumanStreamerV3()
        
        print(f"\n📊 Loaded Data:")
        print(f"• Channels: {len(app.channels)}")
        print(f"• Mapped channels: {len(app.channel_mapping)}")
        print(f"• Baseline sequence: {app.baseline_sequence.shape}")
        
        # Generate turn sequences
        print(f"\n🔄 Generating Turn Sequences...")
        left_turn = app.generate_turn_sequence(app.left_turn_model, 2.0)
        right_turn = app.generate_turn_sequence(app.right_turn_model, 2.0)
        
        print(f"• Left turn sequence: {left_turn.shape}")
        print(f"• Right turn sequence: {right_turn.shape}")
        
        # Analyze signal variations
        print(f"\n📈 Signal Variation Analysis:")
        print("-" * 40)
        
        signal_variations = []
        
        for i, channel in enumerate(app.channels):
            source_column = channel['source_column']
            osc_address = channel['osc_address']
            
            if source_column in app.channel_mapping:
                feature_idx = app.channel_mapping[source_column]
                
                # Get baseline values
                baseline_values = app.baseline_sequence[:, feature_idx]
                
                # Get left turn values
                left_values = left_turn[:, feature_idx]
                
                # Get right turn values  
                right_values = right_turn[:, feature_idx]
                
                # Calculate variations
                baseline_std = np.std(baseline_values)
                left_std = np.std(left_values)
                right_std = np.std(right_values)
                
                # Calculate range (max - min)
                baseline_range = np.max(baseline_values) - np.min(baseline_values)
                left_range = np.max(left_values) - np.min(left_values)
                right_range = np.max(right_values) - np.min(right_values)
                
                # Calculate change from baseline
                left_change = np.mean(np.abs(left_values - baseline_values))
                right_change = np.mean(np.abs(right_values - baseline_values))
                
                # Overall variation score
                variation_score = (left_std + right_std + left_change + right_change) / 4
                
                signal_variations.append({
                    'osc_address': osc_address,
                    'source_column': source_column,
                    'variation_score': variation_score,
                    'left_range': left_range,
                    'right_range': right_range,
                    'left_change': left_change,
                    'right_change': right_change
                })
        
        # Sort by variation score
        signal_variations.sort(key=lambda x: x['variation_score'], reverse=True)
        
        print(f"\n🏆 TOP 10 MOST VARIABLE SIGNALS (Best for Testing):")
        print("=" * 60)
        
        for i, signal in enumerate(signal_variations[:10]):
            print(f"{i+1:2d}. {signal['osc_address']}")
            print(f"    Source: {signal['source_column']}")
            print(f"    Variation Score: {signal['variation_score']:.4f}")
            print(f"    Left Range: {signal['left_range']:.3f}")
            print(f"    Right Range: {signal['right_range']:.3f}")
            print(f"    Left Change: {signal['left_change']:.3f}")
            print(f"    Right Change: {signal['right_change']:.3f}")
            print()
        
        # Suggest specific signals for testing
        print(f"🎯 RECOMMENDED SIGNALS FOR UNREAL TESTING:")
        print("=" * 50)
        
        # Find the best signals by category
        spine_signals = [s for s in signal_variations if 'spine' in s['osc_address']]
        pelvis_signals = [s for s in signal_variations if 'pelvis' in s['osc_address']]
        neck_signals = [s for s in signal_variations if 'neck' in s['osc_address']]
        arm_signals = [s for s in signal_variations if 'arm' in s['osc_address']]
        
        categories = [
            ("Spine (Torso Rotation)", spine_signals[:3]),
            ("Pelvis (Core Movement)", pelvis_signals[:3]),
            ("Neck (Head Movement)", neck_signals[:3]),
            ("Arms (Steering Motion)", arm_signals[:3])
        ]
        
        for category_name, signals in categories:
            if signals:
                print(f"\n{category_name}:")
                for signal in signals:
                    print(f"  • {signal['osc_address']} (score: {signal['variation_score']:.3f})")
        
        # Show sample values for the top signal
        if signal_variations:
            top_signal = signal_variations[0]
            feature_idx = app.channel_mapping[top_signal['source_column']]
            
            print(f"\n📊 SAMPLE VALUES FOR TOP SIGNAL:")
            print(f"Signal: {top_signal['osc_address']}")
            print(f"Source: {top_signal['source_column']}")
            print(f"Baseline values: {app.baseline_sequence[:5, feature_idx]}")
            print(f"Left turn values: {left_turn[:5, feature_idx]}")
            print(f"Right turn values: {right_turn[:5, feature_idx]}")
        
        print(f"\n💡 TESTING RECOMMENDATIONS:")
        print("=" * 35)
        print("1. Start with the TOP 3 signals above - they change the most")
        print("2. Monitor these signals in Unreal Engine's OSC receiver")
        print("3. Type 'turn left' and 'turn right' commands to see changes")
        print("4. Look for smooth, continuous value changes over time")
        print("5. Values should range roughly between -180 to +180 degrees")
        
        print(f"\n🔧 UNREAL ENGINE SETUP:")
        print("=" * 25)
        print("• OSC Host: 127.0.0.1")
        print("• OSC Port: 9000 (updated default)")
        print("• Address Pattern: /bone/{bone}/{axis}")
        print("• Data Type: Float (degrees)")
        print("• Rate: 30 FPS")
        
        return signal_variations
        
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        return []

if __name__ == "__main__":
    variations = analyze_signal_variations()
    
    if variations:
        print(f"\n✅ Analysis complete! Found {len(variations)} signals to analyze.")
        print("Use the recommended signals above for testing in Unreal Engine.")
    else:
        print("❌ Analysis failed. Check the error messages above.")
