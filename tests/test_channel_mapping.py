#!/usr/bin/env python3
"""
Test script to verify channel mapping in v2 streamer
"""

import json
import os

def test_channel_mapping():
    """Test the channel mapping functionality"""
    print("Testing channel mapping...")
    
    try:
        # Load channel config
        config_path = "data/processed/channels_steering_from_columns.json"
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        print(f"Loaded {len(config['channels'])} channels from config")
        
        # Load feature names
        with open("data/processed_v2/normalization_params.json", 'r') as f:
            norm_params = json.load(f)
        feature_names = norm_params['feature_columns']
        
        print(f"Loaded {len(feature_names)} features from normalization params")
        
        # Test mapping
        mapped_count = 0
        unmapped_count = 0
        
        print("\nChannel mapping results:")
        print("-" * 50)
        
        for channel in config['channels']:
            address = channel['address']
            feature_name = address.replace('/mh/', '')
            
            try:
                feature_idx = feature_names.index(feature_name)
                print(f"✓ {address} -> {feature_name} (index {feature_idx})")
                mapped_count += 1
            except ValueError:
                print(f"✗ {address} -> {feature_name} (NOT FOUND)")
                unmapped_count += 1
        
        print("-" * 50)
        print(f"Successfully mapped: {mapped_count}")
        print(f"Failed to map: {unmapped_count}")
        print(f"Mapping success rate: {mapped_count/(mapped_count+unmapped_count)*100:.1f}%")
        
        return mapped_count > 0
        
    except Exception as e:
        print(f"Error testing channel mapping: {e}")
        return False

if __name__ == "__main__":
    print("MetaHuman Streamer v2 - Channel Mapping Test")
    print("=" * 60)
    
    if test_channel_mapping():
        print("\n🎉 Channel mapping test passed!")
        print("v2 streamer should now work with Unreal Engine")
    else:
        print("\n⚠️  Channel mapping test failed!")
        print("Check that the config file and feature names match")
