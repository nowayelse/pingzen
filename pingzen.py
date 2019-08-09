#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, os, re, signal
import curses as cs
import threading as tr
from ipaddress import ip_address as isipv4
from subprocess import getoutput
from collections import deque
from shutil import which
from time import sleep

def initpings():
    return [deque([4] * 1000, 1000) for x in range(len(names))]

def pinger(addr):
    while not stop:
        cmd_result = getoutput('fping -c {} -t 250 -r1 -q {}'.format(count, addr))
        res[addrs.index(addr)] = int(''.join(re.findall(r'\d+/(\d+)/\d+|count (4)', cmd_result)[0]))
        sleep(delay * 0.7)

def writepings():
    global pings
    while not stop:
        for i in range(len(names)):
            pings[i].append(res[i])
        sleep(delay * 1.0)

def listenkey():
    global stop, useaddr, count, paused, refresh, pings
    while not stop:
        key = scr.getch()
        if key == ord ('r'):
            pings = initpings()
        if key == ord ('s'):
            stop = True
        if key == ord ('a'):
            useaddr = not useaddr
        if key == ord ('p'):
            paused = not paused
            count = -count
        refresh = True

def signal_handler(sig, frame):
    global stop
    stop = True

if __name__ == '__main__':
    
    # User-specified variables
    bars    = 0; # 0 = terminal width, else max(bars, longest_name, longest_addr)
    delay    = 1; # refresh rate, secs
    
    # Internal variables
    stop    = False
    useaddr = False
    paused  = False
    refresh = False
    count   = 1
    
    # Validation
    if len(sys.argv) == 1 : sys.exit('pass filepath as argument')
    if which('fping') == None : sys.exit('fping is required')
    if not os.path.exists(sys.argv[1]) : sys.exit('config not found')
    try:
        if .1 < delay < 600: pass
    except: delay = 1
    try:
        if 0 <= bars < 1000 and isinstance(bars, int): pass
    except: bars = 0

    # Parse and validate config
    addrs = []
    names = []
    with open(sys.argv[1]) as file:
        for line in file:
            if line[0] == "#" : continue
            if len((line.strip().split(' '))) != 2 : continue
            try:
                isipv4(line.split()[1])
                addrs.append(line.split()[1])
            except: continue
            names.append(line.split()[0])
    if not names : sys.exit('config is blank')
    

    # Init curses
    scr = cs.initscr()
    scr.attron(cs.A_BOLD)
    cs.curs_set(0)
    cs.noecho()
    cs.start_color()
    cs.use_default_colors()
    cs.init_pair(1, cs.COLOR_WHITE, cs.COLOR_RED)
    cs.init_pair(2, cs.COLOR_WHITE, cs.COLOR_GREEN)
    cs.init_pair(3, cs.COLOR_RED, -1)
    cs.init_pair(5, -1, -1)
    
    # Init threads
    minlen = max(len(max(names+addrs, key = len)), bars)
    pings = initpings()
    res = [4] * len(names)
    signal.signal(signal.SIGINT, signal_handler)
    for addr in addrs : tr.Thread(target = pinger, args = (addr,)).start()
    tr.Thread(target = listenkey, args = ()).start()
    tr.Thread(target = writepings, args = ()).start()
    sleep(.1)
    
    # Print color bars
    while not stop:
        clist = addrs if useaddr else names
        ymax, xmax = scr.getmaxyx()
        ylen = min(ymax, len(names))
        xlen = min(xmax, minlen) if bars != 0 else xmax
        for y in range(ylen):
            for x in reversed(range(xlen)):
                try:
                    scr.addch(y, x, '{:{l}.{l}}'.format(clist[y], l=xlen)[x], cs.color_pair(pings[y][x-xlen]+1))
                except(cs.error): pass
            if paused:
                try:
                    scr.addch(y, xlen-1, '{:{l}.{l}}'.format('PAUSED', l=ylen)[y], cs.color_pair(3))
                except(cs.error): pass
        scr.refresh()
        for i in range(10):
            if refresh:
                refresh = False
                break
            sleep(delay/10.0)
    cs.endwin()
