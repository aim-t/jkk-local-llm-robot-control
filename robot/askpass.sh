#!/bin/bash
# Called by ssh to get the robot's password from .env.local. Prints it only to ssh.
grep -E '^[[:space:]]*robot_password[[:space:]]*=' "$ENV_FILE" | tail -1 | cut -d= -f2- | sed -E 's/^[[:space:]"'\'']+|[[:space:]"'\'']+$//g'
