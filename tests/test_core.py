import math
import socket
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from traffic_core import target_rate, make_packet, send_one

class TrafficTests(unittest.TestCase):
    def test_sawtooth_rises_and_resets(self):
        self.assertAlmostEqual(target_rate("Sawtooth", 0, 8, 40, 30), 10)
        self.assertAlmostEqual(target_rate("Sawtooth", 4, 8, 40, 30), 40)
        self.assertAlmostEqual(target_rate("Sawtooth", 8, 8, 40, 30), 10)

    def test_sine(self):
        self.assertAlmostEqual(target_rate("Sine", 0, 8, 40, 30), 40)
        self.assertAlmostEqual(target_rate("Sine", 2, 8, 40, 30), 70)
        self.assertAlmostEqual(target_rate("Sine", 6, 8, 40, 30), 10)

    def test_udp_loopback(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver, \
             socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            receiver.bind(("127.0.0.1", 0))
            receiver.settimeout(2)
            port = receiver.getsockname()[1]
            msg = make_packet(12, 128)
            n = send_one(sender, msg, port=port)
            data, address = receiver.recvfrom(2048)
            self.assertEqual(n, 128)
            self.assertEqual(data, msg)
            self.assertTrue(data.startswith(b"NTG1|"))

if __name__ == "__main__":
    unittest.main()
