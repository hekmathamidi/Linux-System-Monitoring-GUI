# Linux System Health Monitor — GUI Edition

A polished, dark-themed desktop dashboard written in Python and Tkinter for a Linux Essentials / introductory system administration project.

## Features
- Live CPU, RAM, and root disk utilization cards with progress bars
- Hostname, OS, kernel, architecture, Python version, and current user
- Systemd status checks for SSH (`ssh`), Apache (`apache2`), and XRDP (`xrdp`)
- Network interface and default-route information
- Top 10 processes ordered by CPU use
- Automatic refresh every 5 seconds and manual refresh
- Timestamped plain-text health report saved to `~/linux_health_reports`
- Uses Python standard library only; no pip dependencies

## Requirements
- Linux distribution using `/proc` and systemd (e.g., Kali Linux)
- Python 3
- Tkinter package
- Utilities: `ip`, `systemctl`, `ps`

## Install on Kali Linux
```bash
sudo apt update
sudo apt install python3 python3-tk iproute2 procps
```

Apache and XRDP are optional: the dashboard will report their status whether installed or not.

## Run
From the project folder:
```bash
python3 linux_health_monitor_gui.py
```

## Project files
- `linux_health_monitor_gui.py` — main application
- `README.md` — installation and usage
- `PROJECT_DEFENSE.md` — short presentation and project explanation
- `requirements.txt` — note about standard-library dependencies

## Notes
This is a local system monitoring/administration tool. It does not modify service configuration or require root privileges for its ordinary monitoring features. The report is saved under the current user's home directory.
