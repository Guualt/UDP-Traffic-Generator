"""Tkinter sender with a live rate plot. Python 3.9+ / Windows 10 or 11."""
import csv
from datetime import datetime
from pathlib import Path
import queue
import socket
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from traffic_core import target_rate, make_packet, send_one

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "results"
OUT.mkdir(exist_ok=True)
BG, PANEL, INK, MUTED, TEAL, GRID = "#f5f8fa", "#ffffff", "#172b4d", "#67788a", "#0d9488", "#e5ebf0"

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Network Traffic Generator | UDP Lab")
        self.root.geometry("1060x750")
        self.root.minsize(860, 650)
        self.root.configure(bg=BG)
        self.events = queue.Queue()
        self.stop_event = threading.Event()
        self.worker = None
        self.history = []
        self.sent_total = 0
        self.received_updates = 0
        self.wave = tk.StringVar(value="Sawtooth")
        self.base = tk.StringVar(value="40")
        self.amp = tk.StringVar(value="30")
        self.period = tk.StringVar(value="8")
        self.duration = tk.StringVar(value="24")
        self.packet_size = tk.StringVar(value="128")
        self.port = tk.StringVar(value="9999")
        self.status = tk.StringVar(value="Ready · Start receiver first")
        self.total_label = tk.StringVar(value="0")
        self.rate_label = tk.StringVar(value="0.0 pps")
        self.file_label = tk.StringVar(value="No data yet")
        self.build()
        self.root.after(100, self.poll)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def build(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TCombobox", padding=5)
        style.configure("TEntry", padding=5)
        tk.Label(self.root, text="NETWORK LAB  /  COURSE PROJECT 02",
                 bg=BG, fg=TEAL, font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=30, pady=(20, 2))
        tk.Label(self.root, text="UDP Traffic Generator", bg=BG, fg=INK,
                 font=("Segoe UI", 23, "bold")).pack(anchor="w", padx=30)
        tk.Label(self.root, text="Generate real loopback UDP packets with periodic waveform-shaped rates.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", padx=30, pady=(0, 12))
        config = tk.Frame(self.root, bg=PANEL, padx=15, pady=14, highlightbackground=GRID, highlightthickness=1)
        config.pack(fill="x", padx=30, pady=(0, 10))
        fields = [
            ("Waveform", self.wave, ("Sawtooth", "Sine")),
            ("Target IP", None, None),
            ("UDP Port", self.port, None),
            ("Base (pps)", self.base, None),
            ("Amplitude (pps)", self.amp, None),
            ("Period (sec)", self.period, None),
            ("Duration (sec)", self.duration, None),
            ("Packet bytes", self.packet_size, None),
        ]
        self.entries = []
        for col, (label, var, opts) in enumerate(fields):
            r, c = divmod(col, 4)
            container = tk.Frame(config, bg=PANEL)
            container.grid(row=r, column=c, sticky="ew", padx=8, pady=6)
            tk.Label(container, text=label, bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w")
            if label == "Target IP":
                w = ttk.Entry(container, width=16)
                w.insert(0, "127.0.0.1")
                w.configure(state="readonly")
            elif opts:
                w = ttk.Combobox(container, width=15, textvariable=var, values=opts, state="readonly")
            else:
                w = ttk.Entry(container, width=17, textvariable=var)
            w.pack(fill="x", pady=(4, 0))
            self.entries.append(w)
        for c in range(4): config.grid_columnconfigure(c, weight=1)
        actions = tk.Frame(self.root, bg=BG)
        actions.pack(fill="x", padx=30, pady=5)
        self.start_btn = tk.Button(actions, text="▶  START SENDING", bg=TEAL, fg="white",
                                   font=("Segoe UI", 10, "bold"), relief="flat",
                                   padx=20, pady=10, command=self.start)
        self.start_btn.pack(side="left")
        self.stop_btn = tk.Button(actions, text="■  STOP", bg="#dfe9ec", fg=INK,
                                  font=("Segoe UI", 10, "bold"), relief="flat",
                                  padx=18, pady=10, command=self.stop, state="disabled")
        self.stop_btn.pack(side="left", padx=10)
        tk.Label(actions, textvariable=self.status, bg=BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=12)
        summary = tk.Frame(self.root, bg=BG)
        summary.pack(fill="x", padx=30, pady=(8, 10))
        self.metric(summary, "TOTAL UDP PACKETS SENT", self.total_label, 0)
        self.metric(summary, "ACTUAL LAST-SECOND RATE", self.rate_label, 1)
        self.metric(summary, "RESULTS FILE", self.file_label, 2)
        chart_panel = tk.Frame(self.root, bg=PANEL, highlightthickness=1, highlightbackground=GRID)
        chart_panel.pack(fill="both", expand=True, padx=30, pady=(0, 10))
        tk.Label(chart_panel, text="Actual sending rate  /  Packets per second",
                 bg=PANEL, fg=INK, font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=16, pady=(13, 0))
        self.canvas = tk.Canvas(chart_panel, bg=PANEL, highlightthickness=0, height=270)
        self.canvas.pack(fill="both", expand=True, padx=12, pady=8)
        self.canvas.bind("<Configure>", lambda event: self.draw())
        foot = tk.Frame(self.root, bg=BG)
        foot.pack(fill="x", padx=30, pady=(0, 12))
        tk.Label(foot, text="Safety: 127.0.0.1 only · Max 200 pps · CSV saved to results/",
                 bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w")
        self.draw()

    def metric(self, parent, title, value, column):
        box = tk.Frame(parent, bg=PANEL, padx=15, pady=12, highlightbackground=GRID, highlightthickness=1)
        box.grid(row=0, column=column, sticky="nsew", padx=(0, 10) if column < 2 else 0)
        parent.grid_columnconfigure(column, weight=1)
        tk.Label(box, text=title, bg=PANEL, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w")
        tk.Label(box, textvariable=value, bg=PANEL, fg=INK, font=("Segoe UI", 14, "bold"),
                 wraplength=290, justify="left").pack(anchor="w", pady=(6, 0))

    def read_config(self):
        values = {
            "wave": self.wave.get(),
            "base": float(self.base.get()), "amp": float(self.amp.get()),
            "period": float(self.period.get()), "duration": float(self.duration.get()),
            "size": int(self.packet_size.get()), "port": int(self.port.get())
        }
        if not 1 <= values["port"] <= 65535: raise ValueError("Port must be 1..65535")
        if not 64 <= values["size"] <= 1400: raise ValueError("Packet bytes must be 64..1400")
        if not 0 <= values["base"] <= 200 or not 0 <= values["amp"] <= 200:
            raise ValueError("Base/amplitude must be 0..200")
        if values["base"] + values["amp"] > 200: raise ValueError("Peak must not exceed 200 pps")
        if not 1 <= values["period"] <= 120: raise ValueError("Period must be 1..120 sec")
        if not 1 <= values["duration"] <= 600: raise ValueError("Duration must be 1..600 sec")
        return values

    def start(self):
        if self.worker and self.worker.is_alive(): return
        try: config = self.read_config()
        except ValueError as exc:
            messagebox.showerror("Invalid settings", str(exc)); return
        self.history = []
        self.sent_total = 0
        self.total_label.set("0")
        self.rate_label.set("0.0 pps")
        self.file_label.set("Working…")
        self.draw()
        self.stop_event.clear()
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status.set("Sending real UDP packets…")
        self.worker = threading.Thread(target=self.run_sender, args=(config,), daemon=True)
        self.worker.start()

    def run_sender(self, cfg):
        filename = "sender_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".csv"
        path = OUT / filename
        seq, credit, actual_window = 0, 0.0, 0
        start = time.monotonic()
        previous = start
        next_sample = 1
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock, \
                 path.open("w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle)
                writer.writerow(["elapsed_s", "target_pps", "actual_pps", "cumulative_packets", "waveform"])
                while not self.stop_event.is_set():
                    now = time.monotonic()
                    elapsed = now - start
                    if elapsed >= cfg["duration"]: break
                    dt = min(now - previous, .25)
                    previous = now
                    rate = target_rate(cfg["wave"], elapsed, cfg["period"], cfg["base"], cfg["amp"])
                    credit += rate * max(0, dt)
                    quota = min(int(credit), 100)
                    for _ in range(quota):
                        seq += 1
                        send_one(sock, make_packet(seq, cfg["size"]), port=cfg["port"])
                        actual_window += 1
                    credit -= quota
                    if elapsed >= next_sample:
                        row = (next_sample, round(rate, 2), actual_window, seq, cfg["wave"])
                        writer.writerow(row)
                        handle.flush()
                        self.events.put(("sample", row))
                        actual_window = 0
                        next_sample += 1
                    time.sleep(.01)
                if actual_window:
                    final_elapsed = round(time.monotonic() - start, 2)
                    row = (final_elapsed, round(target_rate(cfg["wave"], final_elapsed, cfg["period"], cfg["base"], cfg["amp"]), 2),
                           actual_window, seq, cfg["wave"])
                    writer.writerow(row)
                    self.events.put(("sample", row))
                self.events.put(("done", filename, seq, self.stop_event.is_set()))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "sample":
                    _, row = event
                    self.history.append(row)
                    self.sent_total = int(row[3])
                    self.total_label.set(f"{self.sent_total:,}")
                    self.rate_label.set(f"{row[2]:.1f} pps")
                    self.draw()
                elif event[0] == "done":
                    _, name, total, interrupted = event
                    self.total_label.set(f"{total:,}")
                    self.file_label.set(name)
                    self.status.set("Stopped by user" if interrupted else "Completed successfully")
                    self.start_btn.config(state="normal")
                    self.stop_btn.config(state="disabled")
                elif event[0] == "error":
                    self.status.set("Error: " + event[1])
                    self.start_btn.config(state="normal")
                    self.stop_btn.config(state="disabled")
                    messagebox.showerror("UDP Error", event[1])
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def draw(self):
        c = self.canvas
        if not c.winfo_exists(): return
        c.delete("all")
        w = max(500, c.winfo_width()); h = max(180, c.winfo_height())
        left, top, right, bottom = 49, 18, w-18, h-33
        max_y = max(20, max((max(r[1], r[2]) for r in self.history), default=80) * 1.2)
        for n in range(5):
            y = bottom - (bottom-top)*n/4
            c.create_line(left, y, right, y, fill=GRID)
            c.create_text(left-9, y, text=str(int(max_y*n/4)), anchor="e",
                          fill=MUTED, font=("Segoe UI", 9))
        c.create_text(left, h-12, text="0s", anchor="w", fill=MUTED, font=("Segoe UI", 9))
        if not self.history:
            c.create_text((left+right)/2, (top+bottom)/2,
                          text="Press START to display live UDP traffic",
                          fill=MUTED, font=("Segoe UI", 12))
            return
        max_t = max(10, float(self.history[-1][0]))
        c.create_text(right, h-12, text=f"{max_t:.0f}s", anchor="e", fill=MUTED, font=("Segoe UI", 9))
        x = lambda t: left + (right-left)*float(t)/max_t
        y = lambda v: bottom - (bottom-top)*float(v)/max_y
        target, actual = [], []
        # Include origin to make the first sample visible.
        for r in self.history:
            target.extend((x(r[0]), y(r[1])))
            actual.extend((x(r[0]), y(r[2])))
        if len(target) >= 4:
            c.create_line(*target, fill="#94a3b8", width=2, dash=(5, 4), smooth=False)
            c.create_line(*actual, fill=TEAL, width=3, smooth=False)
        else:
            c.create_oval(x(self.history[0][0])-3,y(self.history[0][2])-3,
                          x(self.history[0][0])+3,y(self.history[0][2])+3,fill=TEAL,outline="")
        c.create_text(right-8, top+6, text="— Actual     - - Target",
                      fill=TEAL, font=("Segoe UI", 10), anchor="ne")

    def stop(self): self.stop_event.set(); self.status.set("Stopping…")
    def close(self):
        self.stop_event.set()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
