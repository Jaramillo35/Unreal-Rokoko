#!/usr/bin/env python3
"""
Test script for MetaHuman Streamer v2
Tests OSC communication and data streaming
"""

import numpy as np
import json
import os
from pythonosc import udp_client

def test_osc_communication():
    """Test OSC communication"""
    print("Testing OSC communication...")
    
    # Create OSC client
    client = udp_client.SimpleUDPClient("127.0.0.1", 7000)
    
    # Test basic OSC message
    try:
        client.send_message("/test", 1.0)
        print("✓ OSC client created successfully")
    except Exception as e:
        print(f"✗ OSC communication failed: {e}")
        return False
    
    return True

def test_data_loading():
    """Test loading of processed data"""
    print("Testing data loading...")
    
    try:
        # Load normalization parameters
        with open("data/processed_v2/normalization_params.json", 'r') as f:
            norm_params = json.load(f)
        print(f"✓ Loaded normalization params: {len(norm_params['mean'])} features")
        
        # Load baseline data
        baseline_data = np.load("data/processed_v2/baseline_data.npy")
        print(f"✓ Loaded baseline data: {baseline_data.shape}")
        
        # Load turn data
        left_data = np.load("data/processed_v2/left_turn_data.npy")
        right_data = np.load("data/processed_v2/right_turn_data.npy")
        print(f"✓ Loaded turn data - Left: {left_data.shape}, Right: {right_data.shape}")
        
        # Load baseline vector
        baseline_vector = np.load("data/processed_v2/baseline_vector.npy")
        print(f"✓ Loaded baseline vector: {baseline_vector.shape}")
        
        return True
        
    except Exception as e:
        print(f"✗ Data loading failed: {e}")
        return False

def test_data_denormalization():
    """Test data denormalization"""
    print("Testing data denormalization...")
    
    try:
        # Load normalization parameters
        with open("data/processed_v2/normalization_params.json", 'r') as f:
            norm_params = json.load(f)
        
        mean = np.array(norm_params['mean'])
        std = np.array(norm_params['std'])
        
        # Load some normalized data
        baseline_data = np.load("data/processed_v2/baseline_data.npy")
        normalized_frame = baseline_data[0, 0, :]  # First frame of first sample
        
        # Denormalize
        denormalized = (normalized_frame * std) + mean
        
        print(f"✓ Denormalization successful")
        print(f"  Normalized range: [{normalized_frame.min():.3f}, {normalized_frame.max():.3f}]")
        print(f"  Denormalized range: [{denormalized.min():.3f}, {denormalized.max():.3f}]")
        
        return True
        
    except Exception as e:
        print(f"✗ Denormalization failed: {e}")
        return False

def test_sequence_generation():
    """Test sequence generation for different movements"""
    print("Testing sequence generation...")
    
    try:
        # Load data
        baseline_data = np.load("data/processed_v2/baseline_data.npy")
        left_data = np.load("data/processed_v2/left_turn_data.npy")
        right_data = np.load("data/processed_v2/right_turn_data.npy")
        
        # Test baseline sequence
        baseline_seq = baseline_data[0]  # First sample
        print(f"✓ Baseline sequence: {baseline_seq.shape}")
        
        # Test left turn sequence
        left_seq = left_data[0]  # First sample
        print(f"✓ Left turn sequence: {left_seq.shape}")
        
        # Test right turn sequence
        right_seq = right_data[0]  # First sample
        print(f"✓ Right turn sequence: {right_seq.shape}")
        
        # Check for differences between sequences
        baseline_mean = np.mean(baseline_seq, axis=0)
        left_mean = np.mean(left_seq, axis=0)
        right_mean = np.mean(right_seq, axis=0)
        
        baseline_left_diff = np.mean(np.abs(baseline_mean - left_mean))
        baseline_right_diff = np.mean(np.abs(baseline_mean - right_mean))
        left_right_diff = np.mean(np.abs(left_mean - right_mean))
        
        print(f"✓ Sequence differences:")
        print(f"  Baseline vs Left: {baseline_left_diff:.6f}")
        print(f"  Baseline vs Right: {baseline_right_diff:.6f}")
        print(f"  Left vs Right: {left_right_diff:.6f}")
        
        return True
        
    except Exception as e:
        print(f"✗ Sequence generation failed: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 50)
    print("MetaHuman Streamer v2 - Test Suite")
    print("=" * 50)
    
    tests = [
        test_osc_communication,
        test_data_loading,
        test_data_denormalization,
        test_sequence_generation
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        print()
        if test():
            passed += 1
        print("-" * 30)
    
    print(f"\nTest Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The v2 streamer is ready to use.")
    else:
        print("⚠️  Some tests failed. Please check the errors above.")

if __name__ == "__main__":
    main()
