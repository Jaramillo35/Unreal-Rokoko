#!/usr/bin/env python3
"""
Demo: MetaHuman Streamer v3 - NLP Command Testing
Tests the natural language processing capabilities
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mh_streamer_v3 import NLPCommandParser

def test_nlp_commands():
    """Test various natural language commands"""
    
    print("🧠 MetaHuman Streamer v3 - NLP Command Testing")
    print("=" * 60)
    
    # Initialize the NLP parser
    parser = NLPCommandParser()
    
    # Test commands
    test_commands = [
        # Turn left variations
        "turn left",
        "steer left", 
        "go left",
        "left turn",
        "turn to the left",
        "steer left",
        
        # Turn right variations
        "turn right",
        "steer right",
        "go right", 
        "right turn",
        "turn to the right",
        "steer right",
        
        # Basic position variations
        "basic position",
        "return to baseline",
        "default position",
        "normal position",
        "center position",
        "straighten up",
        "baseline",
        "neutral",
        
        # Stop variations
        "stop",
        "halt",
        "pause",
        "stop turning",
        "end",
        
        # Invalid commands
        "invalid command",
        "hello world",
        "random text",
        "",
        "   ",
    ]
    
    print("\n🔍 Testing NLP Command Recognition:")
    print("-" * 40)
    
    for i, command in enumerate(test_commands, 1):
        action, original_text, confidence = parser.parse_command(command)
        
        # Color coding for results
        if action == 'UNKNOWN':
            status = "❌ UNKNOWN"
        elif action in ['TURN_LEFT', 'TURN_RIGHT', 'BASELINE', 'STOP']:
            status = f"✅ {action}"
        else:
            status = f"⚠️  {action}"
        
        print(f"{i:2d}. '{command:<20}' → {status} (conf: {confidence:.2f})")
    
    print("\n📊 Command Categories:")
    print("-" * 25)
    
    # Group results by action
    results = {}
    for command in test_commands:
        action, _, _ = parser.parse_command(command)
        if action not in results:
            results[action] = []
        results[action].append(command)
    
    for action, commands in results.items():
        print(f"\n{action}:")
        for cmd in commands[:3]:  # Show first 3 examples
            print(f"  • '{cmd}'")
        if len(commands) > 3:
            print(f"  • ... and {len(commands) - 3} more")
    
    print("\n🎯 Key Features:")
    print("-" * 15)
    print("• Case-insensitive matching")
    print("• Multiple synonym support")
    print("• Flexible word order")
    print("• Confidence scoring")
    print("• Unknown command handling")
    
    print("\n💡 Usage Examples:")
    print("-" * 18)
    print("• Type 'turn left' in the GUI text input")
    print("• Press Enter or click 'Send Command'")
    print("• Streamer switches to left turn mode")
    print("• Same 37 bone channels as v2 are targeted")
    print("• Use 'basic position' to return to baseline")

if __name__ == "__main__":
    test_nlp_commands()
