# Linux System Health Monitoring Tool (Python)

A menu-driven Python project for Kali Linux developed as part of the Linux Essentials for Cyber Security course. It monitors basic system information and resource usage, displays network details and service status, lists top processes, and generates a timestamped report.

## Features
- System information: hostname, kernel, OS, uptime, and current user
- CPU utilization estimate (sampled over one second)
- RAM usage from `/proc/meminfo`
- Root disk usage
- Network interfaces and default route
- SSH and Apache systemd service status
- Top 10 processes sorted by CPU usage
- Timestamped text report saved in `~/linux_health_reports/`

## Requirements
- Kali Linux or another Linux distribution
- Python 3
- Common Linux utilities: `ip`, `systemctl`, `ps`, and `df`

The Python program uses only Python's standard library; it does not require pip packages.

## Run
```bash
python3 linux_health_monitor.py
```

## Report location
Generated reports are saved under:
```text
~/linux_health_reports/
```

## Demonstration
1. Run the application.
2. Show system information.
3. Show CPU and RAM readings.
4. Display disk space and network configuration.
5. Check SSH and Apache status.
6. Show the top processes.
7. Generate a report and view it with:
   ```bash
   ls -l ~/linux_health_reports
   cat ~/linux_health_reports/health_report_*.txt
   ```

## Concepts demonstrated
- Python functions, variables, conditionals, loops
- Standard-library modules: `os`, `platform`, `subprocess`, `shutil`, `datetime`, `pathlib`
- Reading Linux virtual files `/proc/stat`, `/proc/meminfo`, and `/proc/uptime`
- Calling Linux commands safely through `subprocess`
- File and report handling
- Exception handling

## Limitations
- CPU usage is an approximate one-second sample.
- Service checks query systemd for the named services `ssh` and `apache2`.
- The tool monitors the local computer, not remote hosts.
- Health thresholds are simple project-level indicators, not a production monitoring system.
