#!/bin/bash
# Configure static IP for direct Ethernet connection to laptop
# Run once on the Raspberry Pi

sudo tee /etc/dhcpcd.conf.d/static-eth0.conf > /dev/null <<EOF
interface eth0
static ip_address=192.168.1.2/24
EOF

echo "Static IP 192.168.1.2 configured on eth0."
echo "On the laptop, set its Ethernet interface to 192.168.1.1/24."
echo "Reboot or run: sudo systemctl restart dhcpcd"
