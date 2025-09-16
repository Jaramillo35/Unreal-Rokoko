"""
Tests for the NLP Parser
"""

import pytest
from osc_streamer_v3.parser import NLPParser
from osc_streamer_v3.config import Config
from osc_streamer_v3.intents import TurnIntent, UnknownIntent, HelpIntent, QuitIntent


class TestNLPParser:
    """Test cases for NLPParser"""
    
    @pytest.fixture
    def parser(self):
        """Create parser instance for testing"""
        config = Config.load_from_file()
        return NLPParser(config)
    
    def test_turn_left_basic(self, parser):
        """Test basic turn left command"""
        intent = parser.parse("turn left")
        assert isinstance(intent, TurnIntent)
        assert intent.scope == "body"
        assert intent.direction == "left"
        assert intent.angle_deg == 15.0  # default
        assert intent.speed_deg_s == 90.0  # default
        assert intent.duration_s is None
    
    def test_turn_right_with_angle(self, parser):
        """Test turn right with specific angle"""
        intent = parser.parse("turn right 30 degrees")
        assert isinstance(intent, TurnIntent)
        assert intent.scope == "body"
        assert intent.direction == "right"
        assert intent.angle_deg == 30.0
        assert intent.speed_deg_s == 90.0  # default
        assert intent.duration_s is None
    
    def test_turn_with_speed_and_duration(self, parser):
        """Test turn with speed and duration"""
        intent = parser.parse("rotate body 90 degrees left at 120 deg/s for 0.5s")
        assert isinstance(intent, TurnIntent)
        assert intent.scope == "body"
        assert intent.direction == "left"
        assert intent.angle_deg == 90.0
        assert intent.speed_deg_s == 120.0
        assert intent.duration_s == 0.5
    
    def test_head_turn(self, parser):
        """Test head turn command"""
        intent = parser.parse("turn head right for 0.5s")
        assert isinstance(intent, TurnIntent)
        assert intent.scope == "head"
        assert intent.direction == "right"
        assert intent.angle_deg == 15.0  # default
        assert intent.speed_deg_s == 90.0  # default
        assert intent.duration_s == 0.5
    
    def test_look_left_a_little(self, parser):
        """Test look left with modifier"""
        intent = parser.parse("look left a little")
        assert isinstance(intent, TurnIntent)
        assert intent.scope == "head"
        assert intent.direction == "left"
        assert intent.angle_deg == 5.0  # "a little" modifier
        assert intent.speed_deg_s == 90.0  # default
        assert intent.duration_s is None
    
    def test_synonyms(self, parser):
        """Test synonym normalization"""
        # Test various synonyms for left
        for text in ["turn left", "turn counterclockwise", "turn ccw", "face left"]:
            intent = parser.parse(text)
            assert isinstance(intent, TurnIntent)
            assert intent.direction == "left"
        
        # Test various synonyms for right
        for text in ["turn right", "turn clockwise", "turn cw", "face right"]:
            intent = parser.parse(text)
            assert isinstance(intent, TurnIntent)
            assert intent.direction == "right"
    
    def test_speed_modifiers(self, parser):
        """Test speed modifiers"""
        intent = parser.parse("turn left slowly")
        assert isinstance(intent, TurnIntent)
        assert intent.speed_deg_s == 30.0  # slowly modifier
        
        intent = parser.parse("turn right quickly")
        assert isinstance(intent, TurnIntent)
        assert intent.speed_deg_s == 270.0  # quickly modifier
    
    def test_angle_modifiers(self, parser):
        """Test angle modifiers"""
        intent = parser.parse("turn left a little")
        assert isinstance(intent, TurnIntent)
        assert intent.angle_deg == 5.0  # "a little" modifier
        
        intent = parser.parse("turn right a lot")
        assert isinstance(intent, TurnIntent)
        assert intent.angle_deg == 60.0  # "a lot" modifier
    
    def test_help_command(self, parser):
        """Test help command"""
        intent = parser.parse(":help")
        assert isinstance(intent, HelpIntent)
        
        intent = parser.parse("help")
        assert isinstance(intent, HelpIntent)
    
    def test_quit_command(self, parser):
        """Test quit command"""
        intent = parser.parse(":quit")
        assert isinstance(intent, QuitIntent)
        
        intent = parser.parse("quit")
        assert isinstance(intent, QuitIntent)
    
    def test_unknown_command(self, parser):
        """Test unknown command"""
        intent = parser.parse("do something weird")
        assert isinstance(intent, UnknownIntent)
        assert "do something weird" in intent.original_text
        assert "No matching pattern" in intent.reason
    
    def test_empty_input(self, parser):
        """Test empty input"""
        intent = parser.parse("")
        assert isinstance(intent, UnknownIntent)
        assert intent.reason == "Empty input"
        
        intent = parser.parse("   ")
        assert isinstance(intent, UnknownIntent)
        assert intent.reason == "Empty input"
    
    def test_angle_clamping(self, parser):
        """Test angle clamping to limits"""
        # Test angle too high
        intent = parser.parse("turn left 200 degrees")
        assert isinstance(intent, TurnIntent)
        assert intent.angle_deg == 180.0  # clamped to max
        
        # Test angle too low
        intent = parser.parse("turn left -10 degrees")
        assert isinstance(intent, TurnIntent)
        assert intent.angle_deg == 0.0  # clamped to min
    
    def test_speed_clamping(self, parser):
        """Test speed clamping to limits"""
        # Test speed too high
        intent = parser.parse("turn left 30 degrees at 500 deg/s")
        assert isinstance(intent, TurnIntent)
        assert intent.speed_deg_s == 360.0  # clamped to max
        
        # Test speed too low
        intent = parser.parse("turn left 30 degrees at 0.5 deg/s")
        assert isinstance(intent, TurnIntent)
        assert intent.speed_deg_s == 1.0  # clamped to min
    
    def test_duration_clamping(self, parser):
        """Test duration clamping to limits"""
        # Test duration too high
        intent = parser.parse("turn left 30 degrees for 20 seconds")
        assert isinstance(intent, TurnIntent)
        assert intent.duration_s == 10.0  # clamped to max
        
        # Test duration too low
        intent = parser.parse("turn left 30 degrees for -1 seconds")
        assert isinstance(intent, TurnIntent)
        assert intent.duration_s == 0.0  # clamped to min
    
    def test_help_examples(self, parser):
        """Test that help examples are provided"""
        examples = parser.get_help_examples()
        assert isinstance(examples, list)
        assert len(examples) > 0
        assert "turn left" in examples
        assert "turn right 30 degrees" in examples
