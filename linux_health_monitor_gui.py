#!/usr/bin/env python3
"""
Linux System Health Monitor — GUI Edition
A lightweight Tkinter dashboard for Linux system health, network details,
processes, systemd services (SSH, Apache, XRDP), and report generation.
"""

import datetime as dt
import os
import platform
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

APP_NAME = "Linux System Health Monitor"
REPORT_DIR = Path.home() / "linux_health_reports"
REFRESH_MS = 5000


def run_command(command, timeout=5):
    """Run a command without a shell and return its stdout or a safe message."""
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, check=False
        )
        if result.returncode == 0:
            return result.stdout.strip() or "(No output)"
        return result.stderr.strip() or f"Command exited with code {result.returncode}"
    except FileNotFoundError:
        return f"Required command not found: {command[0]}"
    except subprocess.TimeoutExpired:
        return f"Command timed out: {' '.join(command)}"
    except Exception as exc:
        return f"Unable to run command: {exc}"


def cpu_counters():
    """Read aggregate CPU counters from /proc/stat."""
    try:
        with open("/proc/stat", "r", encoding="utf-8") as file:
            values = [int(value) for value in file.readline().split()[1:]]
        total = sum(values)
        idle = values[3] + (values[4] if len(values) > 4 else 0)
        return total, idle
    except (OSError, ValueError, IndexError):
        return None


def cpu_percent(previous, current):
    """Calculate CPU utilization from two counter samples."""
    if not previous or not current:
        return None
    total_delta = current[0] - previous[0]
    idle_delta = current[1] - previous[1]
    if total_delta <= 0:
        return None
    return max(0.0, min(100.0, 100.0 * (total_delta - idle_delta) / total_delta))


def memory_stats():
    """Return memory total, available, used, and percentage from /proc/meminfo."""
    try:
        values = {}
        with open("/proc/meminfo", "r", encoding="utf-8") as file:
            for line in file:
                key, value = line.split(":", 1)
                if key in ("MemTotal", "MemAvailable"):
                    values[key] = int(value.strip().split()[0])  # kB
        total = values["MemTotal"]
        available = values["MemAvailable"]
        used = total - available
        return total, available, used, (used / total * 100 if total else 0.0)
    except (OSError, ValueError, KeyError, IndexError):
        return None


def disk_stats(path="/"):
    try:
        usage = shutil.disk_usage(path)
        percent = usage.used / usage.total * 100 if usage.total else 0.0
        return usage.total, usage.used, usage.free, percent
    except OSError:
        return None


def service_state(service):
    """Get systemd service state; distinguishes not-found from inactive."""
    result = run_command(["systemctl", "is-active", service])
    if result == "active":
        return "ACTIVE"
    if result == "inactive":
        return "INACTIVE"
    if result == "failed":
        return "FAILED"
    if result in ("unknown", "Unit " + service + ".service could not be found."):
        return "NOT INSTALLED"
    if result.startswith("Required command not found"):
        return "SYSTEMCTL UNAVAILABLE"
    return "UNKNOWN"


def network_details():
    addresses = run_command(["ip", "-brief", "address", "show"])
    route = run_command(["ip", "route", "show", "default"])
    return f"INTERFACES\\n{addresses}\\n\\nDEFAULT ROUTE\\n{route}"


def process_details(limit=10):
    output = run_command(
        ["ps", "-eo", "pid,comm,%cpu,%mem", "--sort=-%cpu"], timeout=5
    )
    if output.startswith("Required command not found") or output.startswith("Unable"):
        return output
    return "\\n".join(output.splitlines()[: limit + 1])


def format_bytes(value):
    value = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TiB"


class HealthMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("1000x760")
        self.root.minsize(820, 640)
        self.root.configure(bg="#0b1220")

        self.cpu_previous = cpu_counters()
        self.cpu_value = None
        self.ram_data = None
        self.disk_data = None
        self.services = {}
        self.network_text = "Loading network information..."
        self.process_text = "Loading process information..."
        self.last_updated = "Not yet updated"
        self.refresh_busy = False

        self.setup_style()
        self.build_ui()
        self.refresh_data()
        self.root.after(REFRESH_MS, self.auto_refresh)

    def setup_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#0b1220")
        style.configure("Panel.TFrame", background="#111c2e")
        style.configure("TLabel", background="#111c2e", foreground="#e5edf8",
                        font=("DejaVu Sans", 10))
        style.configure("Muted.TLabel", background="#111c2e", foreground="#91a4bd",
                        font=("DejaVu Sans", 9))
        style.configure("Title.TLabel", background="#0b1220", foreground="#f1f5f9",
                        font=("DejaVu Sans", 20, "bold"))
        style.configure("Subtitle.TLabel", background="#0b1220", foreground="#9fb0c7",
                        font=("DejaVu Sans", 10))
        style.configure("CardTitle.TLabel", background="#111c2e", foreground="#91a4bd",
                        font=("DejaVu Sans", 9, "bold"))
        style.configure("Metric.TLabel", background="#111c2e", foreground="#f8fafc",
                        font=("DejaVu Sans", 19, "bold"))
        style.configure("Status.TLabel", background="#111c2e", foreground="#cbd5e1",
                        font=("DejaVu Sans", 10, "bold"))
        style.configure("TProgressbar", troughcolor="#26354a", background="#38bdf8",
                        bordercolor="#26354a", lightcolor="#38bdf8", darkcolor="#38bdf8")
        style.configure("Accent.TButton", font=("DejaVu Sans", 10, "bold"),
                        padding=(12, 8))
        style.configure("TButton", font=("DejaVu Sans", 9), padding=(10, 7))
        style.configure("Treeview", background="#111c2e", foreground="#e5edf8",
                        fieldbackground="#111c2e", rowheight=25, borderwidth=0,
                        font=("DejaVu Sans", 9))
        style.configure("Treeview.Heading", background="#26354a", foreground="#e5edf8",
                        font=("DejaVu Sans", 9, "bold"), relief="flat")
        style.map("Treeview", background=[("selected", "#1d4ed8")])

    def panel(self, parent, title):
        frame = ttk.Frame(parent, style="Panel.TFrame", padding=14)
        ttk.Label(frame, text=title.upper(), style="CardTitle.TLabel").pack(anchor="w")
        return frame

    def build_ui(self):
        header = ttk.Frame(self.root)
        header.pack(fill="x", padx=22, pady=(20, 12))
        left = ttk.Frame(header)
        left.pack(side="left", fill="x", expand=True)
        ttk.Label(left, text="System Health", style="Title.TLabel").pack(anchor="w")
        ttk.Label(left, text="Live overview of your Linux machine",
                  style="Subtitle.TLabel").pack(anchor="w", pady=(4, 0))
        self.clock_label = ttk.Label(header, text="", style="Subtitle.TLabel")
        self.clock_label.pack(side="right", anchor="e")

        # Resource metric cards
        cards = ttk.Frame(self.root)
        cards.pack(fill="x", padx=22, pady=5)
        self.cpu_card = self.panel(cards, "CPU Load")
        self.ram_card = self.panel(cards, "Memory")
        self.disk_card = self.panel(cards, "Root Disk")
        for card in (self.cpu_card, self.ram_card, self.disk_card):
            card.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self.cpu_metric = self.metric(self.cpu_card, "Sampling…")
        self.cpu_bar = self.progress(self.cpu_card)
        self.ram_metric = self.metric("placeholder") if False else self.metric(self.ram_card, "—")
        self.ram_bar = self.progress(self.ram_card)
        self.disk_metric = self.metric(self.disk_card, "—")
        self.disk_bar = self.progress(self.disk_card)

        # System information and services
        middle = ttk.Frame(self.root)
        middle.pack(fill="x", padx=22, pady=5)
        info = self.panel(middle, "System")
        info.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self.info_label = ttk.Label(info, text="Loading…", style="Muted.TLabel",
                                    justify="left")
        self.info_label.pack(anchor="w", pady=(8, 0))

        services = self.panel(middle, "Services")
        services.pack(side="left", fill="both", expand=True)
        self.service_labels = {}
        for service, display in (("ssh", "SSH"), ("apache2", "Apache"), ("xrdp", "XRDP")):
            row = ttk.Frame(services, style="Panel.TFrame")
            row.pack(fill="x", pady=3)
            ttk.Label(row, text=display, width=12).pack(side="left")
            label = ttk.Label(row, text="CHECKING", style="Status.TLabel")
            label.pack(side="right")
            self.service_labels[service] = label

        # Detail tabs
        detail_panel = self.panel(self.root, "Details")
        detail_panel.pack(fill="both", expand=True, padx=22, pady=5)
        notebook = ttk.Notebook(detail_panel)
        notebook.pack(fill="both", expand=True, pady=(8, 0))

        network_tab = ttk.Frame(notebook, style="Panel.TFrame", padding=8)
        process_tab = ttk.Frame(notebook, style="Panel.TFrame", padding=8)
        notebook.add(network_tab, text="Network")
        notebook.add(process_tab, text="Top Processes")

        self.network_textbox = self.make_text(network_tab)
        self.process_textbox = self.make_text(process_tab)

        # Bottom action bar
        actions = ttk.Frame(self.root)
        actions.pack(fill="x", padx=22, pady=(8, 18))
        self.updated_label = ttk.Label(actions, text="Updated: —", style="Subtitle.TLabel")
        self.updated_label.pack(side="left")
        ttk.Button(actions, text="Refresh Now", command=self.refresh_data).pack(side="right")
        ttk.Button(actions, text="Generate Report", style="Accent.TButton",
                   command=self.generate_report).pack(side="right", padx=8)

    def metric(self, parent, initial):
        label = ttk.Label(parent, text=initial, style="Metric.TLabel")
        label.pack(anchor="w", pady=(10, 8))
        return label

    def progress(self, parent):
        bar = ttk.Progressbar(parent, maximum=100, mode="determinate")
        bar.pack(fill="x", pady=(0, 5))
        return bar

    def make_text(self, parent):
        text = tk.Text(parent, height=8, wrap="none", bg="#0b1220",
                       fg="#dbeafe", insertbackground="#e5edf8",
                       font=("DejaVu Sans Mono", 9), relief="flat",
                       padx=10, pady=8)
        yscroll = ttk.Scrollbar(parent, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=yscroll.set)
        text.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")
        text.configure(state="disabled")
        return text

    @staticmethod
    def set_text(widget, value):
        widget.configure(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, value)
        widget.configure(state="disabled")

    def refresh_data(self):
        if self.refresh_busy:
            return
        self.refresh_busy = True
        self.updated_label.config(text="Updating…")

        # Run system commands away from Tk's UI thread.
        threading.Thread(target=self.collect_data, daemon=True).start()

    def collect_data(self):
        current_cpu = cpu_counters()
        cpu = cpu_percent(self.cpu_previous, current_cpu)
        self.cpu_previous = current_cpu

        ram = memory_stats()
        disk = disk_stats()
        service_values = {
            "ssh": service_state("ssh"),
            "apache2": service_state("apache2"),
            "xrdp": service_state("xrdp"),
        }
        network = network_details()
        processes = process_details()

        data = {
            "cpu": cpu, "ram": ram, "disk": disk,
            "services": service_values, "network": network,
            "processes": processes,
            "updated": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.root.after(0, lambda: self.apply_data(data))

    def apply_data(self, data):
        self.cpu_value = data["cpu"]
        self.ram_data = data["ram"]
        self.disk_data = data["disk"]
        self.services = data["services"]
        self.network_text = data["network"]
        self.process_text = data["processes"]
        self.last_updated = data["updated"]

        cpu = data["cpu"]
        if cpu is not None:
            self.cpu_metric.config(text=f"{cpu:.1f}%")
            self.cpu_bar["value"] = cpu
        else:
            self.cpu_metric.config(text="Sampling…")

        ram = data["ram"]
        if ram:
            total, available, used, percent = ram
            self.ram_metric.config(text=f"{percent:.1f}%")
            self.ram_bar["value"] = percent
        else:
            self.ram_metric.config(text="N/A")

        disk = data["disk"]
        if disk:
            total, used, free, percent = disk
            self.disk_metric.config(text=f"{percent:.1f}%")
            self.disk_bar["value"] = percent
        else:
            self.disk_metric.config(text="N/A")

        info = (
            f"Host: {platform.node()}\\n"
            f"OS: {platform.system()} {platform.release()}\\n"
            f"Architecture: {platform.machine()}\\n"
            f"Python: {platform.python_version()}\\n"
            f"User: {os.environ.get('USER', 'Unknown')}"
        )
        self.info_label.config(text=info)

        for service, label in self.service_labels.items():
            status = data["services"].get(service, "UNKNOWN")
            label.config(text=status)
            # Neutral status text; avoid implying service status is a security verdict.
            if status == "ACTIVE":
                label.configure(foreground="#4ade80")
            elif status in ("FAILED", "NOT INSTALLED"):
                label.configure(foreground="#fbbf24")
            else:
                label.configure(foreground="#cbd5e1")

        self.set_text(self.network_textbox, data["network"])
        self.set_text(self.process_textbox, data["processes"])
        self.clock_label.config(text=dt.datetime.now().strftime("%a, %d %b  %H:%M"))
        self.updated_label.config(text=f"Updated: {data['updated']}")
        self.refresh_busy = False

    def auto_refresh(self):
        self.refresh_data()
        self.root.after(REFRESH_MS, self.auto_refresh)

    def report_text(self):
        ram = self.ram_data
        disk = self.disk_data
        lines = [
            f"{APP_NAME} — REPORT",
            "=" * 64,
            f"Generated: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Hostname: {platform.node()}",
            f"OS: {platform.platform()}",
            f"Architecture: {platform.machine()}",
            "",
            "RESOURCE SUMMARY",
            "-" * 64,
            f"CPU: {self.cpu_value:.1f}%" if self.cpu_value is not None else "CPU: N/A",
        ]
        if ram:
            total, available, used, percent = ram
            lines.append(f"RAM: {percent:.1f}% used ({format_bytes(used * 1024)} / {format_bytes(total * 1024)})")
        else:
            lines.append("RAM: N/A")
        if disk:
            total, used, free, percent = disk
            lines.append(f"Root disk: {percent:.1f}% used ({format_bytes(used)} / {format_bytes(total)})")
        else:
            lines.append("Root disk: N/A")
        lines += ["", "SERVICE STATUS", "-" * 64]
        for service in ("ssh", "apache2", "xrdp"):
            lines.append(f"{service}: {self.services.get(service, 'UNKNOWN')}")
        lines += ["", "NETWORK INFORMATION", "-" * 64, self.network_text,
                  "", "TOP PROCESSES", "-" * 64, self.process_text, ""]
        return "\\n".join(lines)

    def generate_report(self):
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = REPORT_DIR / f"health_report_{stamp}.txt"
        try:
            report_path.write_text(self.report_text(), encoding="utf-8")
            messagebox.showinfo("Report saved", f"Report created at:\\n{report_path}")
        except OSError as exc:
            messagebox.showerror("Report error", f"Could not save report:\\n{exc}")


def main():
    root = tk.Tk()
    HealthMonitorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
