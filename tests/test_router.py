"""
Tests for the OSC Router
"""

import pytest
from unittest.mock import Mock, patch
from osc_streamer_v3.router import OSCRouter
from osc_streamer_v3.osc_client import OSCClient
from osc_streamer_v3.intents import TurnIntent, UnknownIntent, HelpIntent, QuitIntent, DryRunIntent


class TestOSCRouter:
    """Test cases for OSCRouter"""
    
    @pytest.fixture
    def mock_osc_client(self):
        """Create mock OSC client"""
        client = Mock(spec=OSCClient)
        client.send_message.return_value = True
        return client
    
    @pytest.fixture
    def router(self, mock_osc_client):
        """Create router with mock OSC client"""
        return OSCRouter(mock_osc_client)
    
    def test_route_turn_body(self, router, mock_osc_client):
        """Test routing turn body intent"""
        intent = TurnIntent(
            scope="body",
            direction="left",
            angle_deg=30.0,
            speed_deg_s=90.0,
            duration_s=1.0
        )
        
        success, message = router.route(intent)
        
        assert success is True
        assert "/cmd/turn" in message
        assert "body left 30.0°" in message
        mock_osc_client.send_message.assert_called_once_with(
            "/cmd/turn", "left", 30.0, 90.0, 1.0
        )
    
    def test_route_turn_head(self, router, mock_osc_client):
        """Test routing turn head intent"""
        intent = TurnIntent(
            scope="head",
            direction="right",
            angle_deg=15.0,
            speed_deg_s=60.0,
            duration_s=None
        )
        
        success, message = router.route(intent)
        
        assert success is True
        assert "/cmd/head_turn" in message
        assert "head right 15.0°" in message
        # Check that send_message was called with the right arguments
        mock_osc_client.send_message.assert_called_once()
        call_args = mock_osc_client.send_message.call_args[0]
        assert call_args[0] == "/cmd/head_turn"
        assert call_args[1] == "right"
        assert call_args[2] == 15.0
        assert call_args[3] == 60.0
        assert call_args[4] is None or call_args[4] != call_args[4]  # NaN check
    
    def test_route_turn_with_nan_duration(self, router, mock_osc_client):
        """Test routing turn with NaN duration"""
        intent = TurnIntent(
            scope="body",
            direction="left",
            angle_deg=45.0,
            speed_deg_s=120.0,
            duration_s=None
        )
        
        success, message = router.route(intent)
        
        assert success is True
        # Check that send_message was called with the right arguments
        mock_osc_client.send_message.assert_called_once()
        call_args = mock_osc_client.send_message.call_args[0]
        assert call_args[0] == "/cmd/turn"
        assert call_args[1] == "left"
        assert call_args[2] == 45.0
        assert call_args[3] == 120.0
        assert call_args[4] is None or call_args[4] != call_args[4]  # NaN check
    
    def test_route_unknown_intent(self, router):
        """Test routing unknown intent"""
        intent = UnknownIntent(
            original_text="unknown command",
            reason="No matching pattern"
        )
        
        success, message = router.route(intent)
        
        assert success is False
        assert "Unknown command" in message
        assert "unknown command" in message
    
    def test_route_help_intent(self, router):
        """Test routing help intent"""
        intent = HelpIntent()
        
        success, message = router.route(intent)
        
        assert success is True
        assert "Available commands" in message
        assert "turn left" in message
    
    def test_route_quit_intent(self, router):
        """Test routing quit intent"""
        intent = QuitIntent()
        
        success, message = router.route(intent)
        
        assert success is True
        assert "Goodbye!" in message
    
    def test_route_dry_run_intent(self, router):
        """Test routing dry run intent"""
        intent = DryRunIntent()
        
        success, message = router.route(intent)
        
        assert success is True
        assert "Dry run mode toggled" in message
    
    def test_osc_send_failure(self, router, mock_osc_client):
        """Test handling of OSC send failure"""
        mock_osc_client.send_message.return_value = False
        
        intent = TurnIntent(
            scope="body",
            direction="left",
            angle_deg=30.0,
            speed_deg_s=90.0,
            duration_s=1.0
        )
        
        success, message = router.route(intent)
        
        assert success is False
        assert "Failed to send" in message
    
    def test_unknown_scope(self, router, mock_osc_client):
        """Test handling of unknown scope"""
        # Test with a scope that's not in the address map
        # We'll test this by temporarily modifying the address map
        original_map = router.address_map.copy()
        router.address_map = {"body": "/cmd/turn"}  # Remove head mapping
        
        intent = TurnIntent(
            scope="head",  # This scope won't be found
            direction="left",
            angle_deg=30.0,
            speed_deg_s=90.0,
            duration_s=1.0
        )
        
        success, message = router.route(intent)
        
        assert success is False
        assert "No OSC address for scope" in message
        
        # Restore original mapping
        router.address_map = original_map
    
    def test_get_osc_schema(self, router):
        """Test getting OSC schema documentation"""
        schema = router.get_osc_schema()
        
        assert "/cmd/turn" in schema
        assert "/cmd/head_turn" in schema
        assert "Arguments:" in schema
        assert "direction:str" in schema
        assert "angle:float" in schema
        assert "speed:float" in schema
        assert "duration:float" in schema
    
    def test_turn_intent_to_osc_args(self):
        """Test TurnIntent.to_osc_args method"""
        # Test with duration
        intent = TurnIntent(
            scope="body",
            direction="left",
            angle_deg=30.0,
            speed_deg_s=90.0,
            duration_s=1.5
        )
        
        args = intent.to_osc_args()
        expected = ("left", 30.0, 90.0, 1.5)
        assert args == expected
        
        # Test without duration (None)
        intent.duration_s = None
        args = intent.to_osc_args()
        # Check that the last argument is NaN
        assert len(args) == 4
        assert args[0] == "left"
        assert args[1] == 30.0
        assert args[2] == 90.0
        assert args[3] is None or args[3] != args[3]  # NaN check
    
    def test_other_intents_to_osc_args(self):
        """Test other intents' to_osc_args methods"""
        # UnknownIntent
        intent = UnknownIntent(original_text="test", reason="reason")
        assert intent.to_osc_args() == ()
        
        # HelpIntent
        intent = HelpIntent()
        assert intent.to_osc_args() == ()
        
        # QuitIntent
        intent = QuitIntent()
        assert intent.to_osc_args() == ()
        
        # DryRunIntent
        intent = DryRunIntent()
        assert intent.to_osc_args() == ()
