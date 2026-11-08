#!/usr/bin/env python3
"""
Linux System Health Monitoring Tool
Course project: Linux Essentials for Cyber Security

A menu-driven, standard-library Python tool for checking local Linux system
information, resource usage, network configuration, service status, and processes.
"""

import datetime
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path

REPORT_DIR = Path.home() / "linux_health_reports"


def print_line():
    """Print a visual separator."""
    print("=" * 40)


def run_command(command, timeout=5):
    """Run a system command safely and return its output, or an error message."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip() or "(No output)"
        return result.stderr.strip() or f"Command returned exit code {result.returncode}"
    except FileNotFoundError:
        return f"Command not found: {command[0]}"
    except subprocess.TimeoutExpired:
        return f"Command timed out: {' '.join(command)}"
    except Exception as exc:
        return f"Error: {exc}"


def system_info():
    """Display basic operating-system and user information."""
    print_line()
    print("SYSTEM INFORMATION")
    print_line()
    print(f"Hostname:       {platform.node() or 'N/A'}")
    print(f"Kernel:         {platform.release() or 'N/A'}")
    print(f"Operating Sys:  {platform.platform() or 'N/A'}")
    print(f"Uptime:         {get_uptime()}")
    print(f"Current User:   {os.environ.get('USER') or os.environ.get('USERNAME') or 'N/A'}")


def get_uptime():
    """Return system uptime in a readable format using /proc/uptime."""
    try:
        with open("/proc/uptime", "r", encoding="utf-8") as file:
            seconds = int(float(file.readline().split()[0]))
        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, _ = divmod(remainder, 60)
        parts = []
        if days:
            parts.append(f"{days} day(s)")
        if hours:
            parts.append(f"{hours} hour(s)")
        parts.append(f"{minutes} minute(s)")
        return ", ".join(parts)
    except (OSError, ValueError, IndexError):
        return run_command(["uptime", "-p"])


def read_cpu_times():
    """Read aggregate CPU counters from the first line of /proc/stat."""
    with open("/proc/stat", "r", encoding="utf-8") as file:
        fields = file.readline().split()
    # fields[0] is 'cpu'; the remaining entries are CPU time counters.
    values = [int(value) for value in fields[1:]]
    idle = values[3] + (values[4] if len(values) > 4 else 0)  # idle + iowait
    total = sum(values)
    return total, idle


def cpu_usage(interval=1.0):
    """Estimate CPU utilization across a short sampling interval."""
    try:
        total_before, idle_before = read_cpu_times()
        time.sleep(interval)
        total_after, idle_after = read_cpu_times()
        total_delta = total_after - total_before
        idle_delta = idle_after - idle_before
        if total_delta <= 0:
            return None
        return 100.0 * (total_delta - idle_delta) / total_delta
    except (OSError, ValueError, IndexError):
        return None


def memory_info():
    """Return RAM total, available, used, and percentage from /proc/meminfo."""
    try:
        values = {}
        with open("/proc/meminfo", "r", encoding="utf-8") as file:
            for line in file:
                key, value = line.split(":", 1)
                if key in ("MemTotal", "MemAvailable"):
                    values[key] = int(value.strip().split()[0])  # KiB
        total = values["MemTotal"]
        available = values["MemAvailable"]
        used = total - available
        percent = (used / total * 100) if total else 0.0
        return total, available, used, percent
    except (OSError, ValueError, KeyError, IndexError):
        return None


def memory_usage():
    """Print RAM usage."""
    data = memory_info()
    if data is None:
        print("RAM information unavailable.")
        return
    total, available, used, percent = data
    print(f"RAM Used: {percent:.1f}% ({used // 1024} MiB used of {total // 1024} MiB total)")


def disk_info(path="/"):
    """Return disk usage for a path."""
    try:
        usage = shutil.disk_usage(path)
        percent = (usage.used / usage.total * 100) if usage.total else 0.0
        return usage, percent
    except OSError:
        return None, None


def disk_usage():
    """Display root filesystem disk usage."""
    usage, percent = disk_info("/")
    if usage is None:
        print("Disk information unavailable.")
        return
    print("Filesystem  Size  Used  Free  Use%")
    print(
        f"/           {format_bytes(usage.total):>5} "
        f"{format_bytes(usage.used):>5} {format_bytes(usage.free):>5} "
        f"{percent:.0f}%"
    )


def format_bytes(number):
    """Format bytes using readable units."""
    value = float(number)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f}{unit}"
        value /= 1024
    return f"{value:.1f}TB"


def network_info():
    """Display interface addresses and the default route."""
    print_line()
    print("NETWORK INFORMATION")
    print_line()
    print("IP addresses:")
    print(run_command(["ip", "-brief", "address", "show"]))
    print()
    print("Default route:")
    route_output = run_command(["ip", "route", "show", "default"])
    if route_output.startswith("Command not found") or not route_output:
        print("No default route found or the ip command is unavailable.")
    else:
        print(route_output)


def service_status(service):
    """Return a readable systemd status for a service."""
    result = run_command(["systemctl", "is-active", service])
    if result == "active":
        return f"{service:<10} : ACTIVE"
    if result.startswith("Command not found"):
        return f"{service:<10} : systemctl not available"
    return f"{service:<10} : INACTIVE, not installed, or status unavailable"


def services_check():
    """Check SSH and Apache service status."""
    print_line()
    print("SERVICE STATUS")
    print_line()
    print(service_status("ssh"))
    print(service_status("apache2"))


def top_processes(limit=10):
    """Return top processes sorted by CPU usage using the ps utility."""
    result = run_command(
        ["ps", "-eo", "pid,comm,%cpu,%mem", "--sort=-%cpu"],
        timeout=5,
    )
    if result.startswith("Command not found") or result.startswith("Error:"):
        return result
    lines = result.splitlines()
    return "\n".join(lines[: limit + 1])  # Include header plus requested process count


def processes():
    """Display the top CPU-consuming processes."""
    print_line()
    print("TOP 10 PROCESSES BY CPU")
    print_line()
    print(top_processes())


def health_summary():
    """Calculate a simple health status using 85% RAM/disk and 90% CPU thresholds."""
    cpu = cpu_usage()
    memory = memory_info()
    disk, disk_percent = disk_info("/")

    ram_percent = memory[3] if memory else None
    status = "NORMAL"

    if (ram_percent is not None and ram_percent >= 85) or (
        disk_percent is not None and disk_percent >= 85
    ):
        status = "WARNING"

    if cpu is not None and cpu >= 90:
        status = "HIGH CPU"

    print(f"CPU Usage:  {cpu:.1f}%" if cpu is not None else "CPU Usage:  N/A")
    print(f"RAM Usage:  {ram_percent:.1f}%" if ram_percent is not None else "RAM Usage:  N/A")
    print(f"Root Disk:  {disk_percent:.1f}%" if disk_percent is not None else "Root Disk:  N/A")
    print(f"Status:     {status}")


def generate_report():
    """Write system checks to a timestamped text report."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORT_DIR / f"health_report_{timestamp}.txt"

    # Capture the report's output by redirecting stdout temporarily.
    import contextlib
    import io

    report_buffer = io.StringIO()
    with contextlib.redirect_stdout(report_buffer):
        print("LINUX SYSTEM HEALTH REPORT")
        print(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        system_info()
        print()
        print_line()
        print("RESOURCE USAGE")
        print_line()
        health_summary()
        print()
        print_line()
        print("DISK SPACE")
        print_line()
        print(run_command(["df", "-hP"]))
        print()
        network_info()
        print()
        services_check()
        print()
        processes()

    try:
        report_path.write_text(report_buffer.getvalue(), encoding="utf-8")
        print()
        print("Report generated successfully:")
        print(report_path)
    except OSError as exc:
        print(f"Could not save report: {exc}")


def show_menu():
    """Clear the terminal and display the main menu."""
    os.system("clear")
    print_line()
    print("      LINUX SYSTEM HEALTH MONITOR")
    print_line()
    print("1. System Information")
    print("2. CPU and RAM Usage")
    print("3. Disk Space")
    print("4. Network Information")
    print("5. Check Services (SSH / Apache)")
    print("6. Top Running Processes")
    print("7. Generate System Report")
    print("8. Exit")
    print_line()


def main():
    """Run the interactive menu loop."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    while True:
        show_menu()
        choice = input("Enter your choice [1-8]: ").strip()

        if choice == "1":
            system_info()
        elif choice == "2":
            cpu = cpu_usage()
            print(f"CPU Usage: {cpu:.1f}%" if cpu is not None else "CPU Usage: N/A")
            memory_usage()
        elif choice == "3":
            disk_usage()
        elif choice == "4":
            network_info()
        elif choice == "5":
            services_check()
        elif choice == "6":
            processes()
        elif choice == "7":
            generate_report()
        elif choice == "8":
            print("Thank you for using Linux System Health Monitor.")
            break
        else:
            print("Invalid choice. Please enter a number from 1 to 8.")

        input("\nPress Enter to return to the menu...")


if __name__ == "__main__":
    main()
