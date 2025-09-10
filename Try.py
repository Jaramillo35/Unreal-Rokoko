from pythonosc.udp_client import SimpleUDPClient
import time

c = SimpleUDPClient("127.0.0.1", 8000)

# 1) Idle channel test: should go down your TRUE branch and hit ChannelValues.Add
c.send_message("/mh/idle/RightWrist_flexion", 15.0)

# 2) Steering helpers: should go down your FALSE branch and set the floats
c.send_message("/mh/steer/right", 0.75)
time.sleep(0.1)
c.send_message("/mh/steer/left", 0.25)