"""UDP traffic scheduling and packet format. Standard library only."""
import math
import socket
import time

MAGIC = b"NTG1|"

def target_rate(waveform, elapsed, period=8.0, base=40.0, amplitude=30.0):
    """Packets per second; sawtooth ascends and resets, sine oscillates."""
    if period <= 0 or base < 0 or amplitude < 0:
        raise ValueError("Invalid waveform parameters")
    phase = (elapsed % period) / period
    if waveform == "Sawtooth":
        rate = base - amplitude + 2.0 * amplitude * phase
    elif waveform == "Sine":
        rate = base + amplitude * math.sin(2.0 * math.pi * phase)
    else:
        raise ValueError("Unknown waveform")
    return max(0.0, rate)

def make_packet(sequence, size=128):
    if size < 64 or size > 1400:
        raise ValueError("Packet size must be 64..1400")
    header = MAGIC + f"{sequence:010d}|{time.time():.6f}|".encode("ascii")
    return header + b"X" * (size - len(header))

def send_one(sock, packet, host="127.0.0.1", port=9999):
    # Restrict this teaching example to the local machine.
    if host != "127.0.0.1":
        raise ValueError("Only local-loopback traffic is supported")
    return sock.sendto(packet, (host, port))
