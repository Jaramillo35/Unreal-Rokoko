from pythonosc.udp_client import SimpleUDPClient
import time
import math

# Change the IP/port if your OSC server in Unreal listens on another port
ip = "127.0.0.1"
port = 9000

client = SimpleUDPClient(ip, port)

print("Sending /mh/RightForeArm_roll test messages...")

# Loop: oscillate the value between -20 and +20 degrees
while True:
    for angle in range(-20, 21, 5):  # -20, -15, ... 20
        client.send_message("/mh/RightForeArm_roll", float(angle))
        print(f"Sent: /mh/RightForeArm_roll {angle}")
        time.sleep(0.2)

    for angle in range(20, -21, -5):  # 20, 15, ... -20
        client.send_message("/mh/LeftForeArm_roll", float(angle))
        print(f"Sent: /mh/LeftForeArm_roll {angle}")
        time.sleep(0.2)