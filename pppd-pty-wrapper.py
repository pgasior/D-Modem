#!/usr/bin/env python3
"""
Find symlinks in /dev and /tmp that point to the current terminal (ttyname).
Start pppd with the first found symlink and passed command line arguments.
"""

import os
import sys
import syslog


def get_ttyname():
    for fd in (sys.stdin, sys.stdout, sys.stderr):
        try:
            if os.isatty(fd.fileno()):
                return os.ttyname(fd.fileno())
        except (AttributeError, OSError):
            continue
    return None


def find_symlinks_to(target, search_dirs):
    matches = []
    target_real = os.path.realpath(target)

    for directory in search_dirs:
        try:
            entries = os.scandir(directory)
        except PermissionError as e:
            msg = f"Permission denied: {directory} ({e})"
            syslog.syslog(syslog.LOG_WARNING, msg)
            continue
        except FileNotFoundError:
            msg = f"Directory not found: {directory}"
            syslog.syslog(syslog.LOG_WARNING, msg)
            continue

        with entries:
            for entry in entries:
                try:
                    if entry.is_symlink():
                        link_real = os.path.realpath(entry.path)
                        if link_real == target_real:
                            matches.append(entry.path)
                except OSError:
                    continue

    return matches


def main():
    syslog.openlog('pppd-pty-wrapper', syslog.LOG_PID, syslog.LOG_DAEMON)
    
    tty = get_ttyname()
    if tty is None:
        msg = "Could not determine tty name (not running in a terminal?)"
        syslog.syslog(syslog.LOG_ERR, msg)
        sys.exit(1)

    tty_real = os.path.realpath(tty)
    syslog.syslog(syslog.LOG_INFO, f"Current tty: {tty} -> {tty_real}")

    search_dirs = ["/dev", "/tmp"]

    matches = find_symlinks_to(tty, search_dirs)

    if matches:
        syslog.syslog(syslog.LOG_INFO, f"Found {len(matches)} symlink(s) pointing to {tty}")
        for link in matches:
            target = os.readlink(link)
            syslog.syslog(syslog.LOG_DEBUG, f"Symlink: {link} -> {target}")
        
        first_symlink = matches[0]
        syslog.syslog(syslog.LOG_INFO, f"Using first symlink: {first_symlink}")
        
        pppd_cmd = ["/usr/sbin/pppd", first_symlink] + sys.argv[1:]
        syslog.syslog(syslog.LOG_INFO, f"Executing: {' '.join(pppd_cmd)}")
        
        try:
            os.execvp(pppd_cmd[0], pppd_cmd)
        except Exception as e:
            msg = f"Error executing pppd: {e}"
            syslog.syslog(syslog.LOG_ERR, msg)
            sys.exit(1)
    else:
        msg = f"No symlinks found pointing to {tty}"
        syslog.syslog(syslog.LOG_ERR, msg)
        sys.exit(1)


if __name__ == "__main__":
    main()