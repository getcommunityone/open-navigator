#!/bin/bash

echo "Creating mount point at /mnt/g..."
sudo mkdir -p /mnt/g

echo "Mounting Windows G: drive to WSL..."
sudo mount -t drvfs G: /mnt/g

echo "Mount complete! You can now access your Google Drive at /mnt/g/"