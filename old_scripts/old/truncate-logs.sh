#!/bin/bash

# Exit on error
set -e

# Truncate all logs in /var/logs
echo "Truncating all logs in /var/log..."
sudo find /var/log -type f -exec truncate -s 0 {} \;
echo "Logs in /var/log have been truncated."

# Reset journalctl logs
echo "Resetting journalctl logs..."
if sudo systemctl is-active --quiet systemd-journald; then
    sudo journalctl --rotate
    sudo journalctl --vacuum-time=1s
    echo "journalctl logs have been reset."
else
    echo "systemd-journald is not running. Skipping journalctl reset."
fi

echo "Log cleanup complete!"
