#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import signal
import argparse
import curses as cs
import threading as tr
from re import findall
from ipaddress import ip_address as isipv4
from subprocess import getoutput
from collections import deque
from shutil import which
from time import sleep
from time import time as now
from scapy.all import *


class Props:
    
    def __init__(self):
        self.flood = False
        self.pause = False
    
    def switchprop(self, prop):
        setattr(self, prop, not getattr(self, prop))
        return getattr(self, prop)


class Target(Props):
    
    def __init__(self, name, addr):
        Props.__init__(self)
        self.alive = True
        self.name = name
        self.addr = addr
        # self.iface = self.__getiface(self.addr)
        self.__lastreport = 2
        self.reportinit()
        self.__pingstart(self.addr)
        tr.Thread(target=self.__reportset, args=()).start()
    
    ''' Not need yet
    def __getiface(self, addr):
        return findall(r'dev (\S+)', getoutput('ip r g {}'.format(addr)))[0]
    '''
    
    def __pingstart(self, addr):
        tr.Thread(target=self.__fping if usefping else self.__sping,
            args=(addr,)).start()
    
    def __fping(self, addr):
        while self.alive:
            self.__lastreport = 2 if self.pause else \
                    int(findall(r'\d+/(\d+)/\d+', getoutput(
                    'fping -c1 -t250 -r0 -q {}'.format(addr)))[0])
            sleep(delay*0.7)
    
    def __sping(self, addr):
        logging.getLogger("scapy.runtime").setLevel(logging.ERROR)
        conf.verb = 0
        conf.logLevel = 0
        pkt = IP(dst=addr)/ICMP()
        while self.alive:
            while self.alive and self.pause:
                self.__lastreport = 2
                sleep(delay*0.7)
            via = (findall(r'via (\S+)',
                    getoutput('ip r g {}'.format(addr)))+[addr])[0]
            ans, _ = arping(via, timeout=delay*0.7)
            while len(ans) >= 1 and self.alive and not self.pause:
                if self.flood:
                    time_start = now()
                    send(pkt, inter=0, count=100, verbose=0)
                    if now()-time_start > 2.0:
                        self.__lastreport = 0
                        ans = []
                    else:
                        self.__lastreport = 4
                else:
                    ans, _ = sr(pkt, retry=0, timeout=delay*0.5, verbose=0)
                    if len(ans) >= 1:
                        self.__lastreport = 1
                        sleep(delay*0.7)
            self.__lastreport = 0
    
    def reportinit(self):
        self.__report = deque([2] * 1000, 1000)
    
    def __reportset(self):
        while self.alive:
            self.__report.append(self.__lastreport)
            sleep(delay * 1.0)
    
    def getreport(self):
        return self.__report


class Zen(Props):
    
    def __init__(self):
        Props.__init__(self)
        self.targets = []
        self.__validate()
        self.configupdate()
        tr.Thread(target=self.check, args=()).start()
        self.sel = None
    
    def __len__(self):
        return len(self.targets)
    
    def __validate(self):
        global delay, bars
        if usefping and not which('fping'):
            terminate('Fping is required')
        try:
            if .1 < delay < 600: pass
        except:
            delay = 1.0
        try:
            if 0 <= bars < 1000 and isinstance(bars, int): pass
        except:
            bars = 0
    
    def configupdate(self):
        names, addrs = [], []
        if not os.path.exists(filename):
            terminate('Config not found')
        with open(filename) as file:
            for line in file:
                if line[0] == "#":
                    continue
                try:
                    name, addr = line.strip().split()[:2]
                except:
                    terminate('Config parse error')
                try:
                    isipv4(addr)
                except:
                    terminate('Some non-ipv4 address found')
                names.append(name)
                addrs.append(addr)
                if (name, addr) not in \
                        [(i.name, i.addr) for i in self.targets]:
                    self.targets.append(Target(name, addr))
        for i in self.targets:
            if (i.name, i.addr) not in \
              [(names[i], addrs[i]) for i in range(len(names))]:
                i.alive = False
        self.__ins = [None]+[i for i in range(len(self.targets))]
    
    def minlen(self):
        return max(len(max(
            [i.name for i in self.targets] + \
            [i.addr for i in self.targets] + [''], key = len)), bars)
    
    def getaddrs(self):
        return [i.addr for i in self.targets]
    
    def getnames(self):
        return [i.name for i in self.targets]
    
    def reselect(self, inc):
        self.sel = self.__ins[(self.__ins.index(self.sel)+inc)%len(self.__ins)]
    
    def reprop(self, prop):
        if self.sel == None:
            state = self.switchprop(prop)
            for i in self.targets:
                setattr(i, prop, state)
        else:
            state = self.targets[self.sel].switchprop(prop)
            if getattr(self, prop) not in \
                    [getattr(i, prop) for i in self.targets]:
                self.switchprop(prop)
    
    def check(self):
        while self.targets:
            for i in self.targets:
                if not i.alive:
                    self.targets.remove(i)
            sleep(0.01)
        terminate()
    
    def delete(self):
        if self.sel != None:
            self.targets[self.sel].alive = False
            self.__ins = [None]+[i for i in range(len(self.targets))]
            self.sel = None
    
    def refresh(self):
        for i in self.targets:
            i.reportinit()

def listenkey():
    global useaddr
    key = scr.getch()
    if key == ord ('a') : useaddr = not useaddr
    if key == ord ('c') : zen.configupdate()
    if key == ord ('f') : zen.reprop('flood')
    if key == ord ('d') : zen.delete()
    if key == ord ('p') : zen.reprop('pause')
    if key == ord ('r') : zen.refresh()
    if key == ord ('s') : terminate()
    if key == (27 and 91 and 65) : zen.reselect(-1)
    if key == (27 and 91 and 66) : zen.reselect(1)

def signal_handler(sig, frame):
    terminate()

def terminate(msg=''):
    global exit_msg
    try:
        for i in zen.targets:
            i.alive = False
    except: pass
    sleep(.1)
    exit_msg = msg
    cs.endwin()
    sys.exit(exit_msg)


if __name__ == '__main__':
    
    ''' Parse command line '''
    helpfile = 'Path to config file with syntax:\n'+ \
            ' <NAME1> <ADDR1>\n#<NAME2> <ADDR2> skipped line\n'+ \
            '...\n <NAMEN> <ADDRN> ["ANY COMMENTS"]\n'
    helpprog = 'Hotkeys:\n'+ \
            '  a  Switch between names and addresses\n'+ \
            '  c  Reread config file\n'+ \
            '  d  Delete target\n'+ \
            '  f  Switch flood mode\n'+ \
            '  p  Un/pause pings\n'+ \
            '  r  Clear pings history\n'+ \
            '     UP/DOWN Arrows to select certain item for flood/pause\n'+ \
            '  s  Exit program, or ctrl-c'
    args = argparse.ArgumentParser(add_help=False, description=helpprog, \
        formatter_class=argparse.RawTextHelpFormatter)
    args.add_argument('-b', action="store", dest="bars", type=int, \
        default=0, help="Columns to fill. 0 for terminal width ")
    args.add_argument('-t', action="store", dest="delay", type=float,\
        default=1.0, help="Delay between ping requests")
    args.add_argument('-o', action="store_true", dest="usefping", \
        help="Use Fping instead of Scapy which needs a root and allows flood")
    args.add_argument('-f', action="store", dest="filename", type=str,\
        default='', help=helpfile)
    globals().update(args.parse_args().__dict__)
    
    if not filename:
        args.print_help()
        sys.exit()
    if not usefping and os.geteuid() != 0:
        sys.exit('Scapy requires root privileges. Use -o for Fping insted')
    
    ''' Specify Internal variables '''
    useaddr = False
    exit_msg = ''
    
    ''' Init curses '''
    scr = cs.initscr()
    scr.attron(cs.A_BOLD)
    scr.timeout(40)
    cs.curs_set(0)
    cs.noecho()
    cs.start_color()
    cs.use_default_colors()
    cs.init_pair(1, cs.COLOR_WHITE, cs.COLOR_RED)    # Reached
    cs.init_pair(2, cs.COLOR_WHITE, cs.COLOR_GREEN)  # Unreached
    cs.init_pair(3, -1, -1)                          # Paused
    cs.init_pair(4, cs.COLOR_RED, -1)                # Paused red
    cs.init_pair(5, cs.COLOR_WHITE, cs.COLOR_YELLOW) # Flooded
    cs.init_pair(6, cs.COLOR_WHITE, cs.COLOR_BLACK)  # Selected
    
    ''' Init threads '''
    zen = Zen()
    signal.signal(signal.SIGINT, signal_handler)
    
    ''' Print color bars '''
    while zen.targets:
        clist = zen.getaddrs() if useaddr else zen.getnames()
        ymax, xmax = scr.getmaxyx()
        ylen = min(ymax, len(zen))
        xlen = min(xmax, zen.minlen()) if bars != 0 else xmax
        scr.clear()
        for y in range(ylen):
            for x in reversed(range(xlen)):
                try:
                    scr.addch(y, x, '{:{l}.{l}}'.format(clist[y], l=xlen)[x], \
                      cs.color_pair(zen.targets[y].getreport()[x-xlen]+1))
                except: pass
        try:
            scr.addch(zen.sel, 0, clist[zen.sel][0], cs.color_pair(6))
        except: pass
        scr.refresh()
        listenkey()
