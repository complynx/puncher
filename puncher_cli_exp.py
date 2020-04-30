import time
import socket
import sys
import json
import threading
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger()
overall_timeout = threading.Event()

threading.Timer(5*60, overall_timeout.set)
threading.Timer(6*60, exit)

try:
    import pyautogui
    from pyautogui import Point
except:
    import subprocess
    import os

    subprocess.call([sys.executable, "-m", "pip", "install", "pyautogui"])
    subprocess.call([sys.executable, os.path.realpath(__file__)])
    exit()

voicemeeterWinTitle = 'VoiceMeeter'
vbanTitle = 'VB-Audio Network Configuration'
puncher_id = "vban_punch_1"
puncher_addr = "complynx.net"
puncher_vban_port = 6981
puncher_comm_port = 6980

minGuiDelay = 0.1

vbanBtnPoint = Point(x=799, y=25)
vbanWinHeader = Point(x=308, y=9)

vbanInEnable1 = Point(x=38, y=166)
vbanInAddr1 = Point(x=266, y=165)
vbanInPort1 = Point(x=382, y=169)

vbanOutEnable1 = Point(x=40, y=539)
vbanOutAddr1 = Point(x=340, y=541)
vbanOutPort1 = Point(x=476, y=540)

vbanEnable = Point(x=30, y=53)

vbanWin = None


def addp(p1, p2):
    return pyautogui.Point(x=p1.x + p2.x, y=p1.y + p2.y)


def subp(p1, p2):
    return pyautogui.Point(x=p1.x - p2.x, y=p1.y - p2.y)


try:
    voicemeeterWin = pyautogui.getAllWindows()[pyautogui.getAllTitles().index(voicemeeterWinTitle)]
    voicemeeterWin.activate()
except ValueError:
    pyautogui.alert("Open VoiceMeeter Banana window before running this program.\nInstall it if it's not installed yet")
    exit(1)


def vbanSetIn(addr, port):
    logger.info("setting vban in to %s:%d", addr, port)
    pyautogui.click(addp(vbanWin.topleft, vbanWinHeader))
    time.sleep(minGuiDelay)
    pyautogui.click(addp(vbanWin.topleft, vbanInAddr1))
    time.sleep(minGuiDelay)
    pyautogui.write(f"{addr}\n")
    time.sleep(minGuiDelay)
    pyautogui.click(addp(vbanWin.topleft, vbanInPort1))
    time.sleep(minGuiDelay)
    pyautogui.write(f"{port}\n")
    time.sleep(minGuiDelay)
    img = pyautogui.screenshot()
    if img.getpixel(addp(vbanWin.topleft, vbanInEnable1))[1] < 100:
        pyautogui.click(addp(vbanWin.topleft, vbanInEnable1))


def vbanSetOut(addr, port):
    logger.info("setting vban out to %s:%d", addr, port)
    pyautogui.click(addp(vbanWin.topleft, vbanWinHeader))
    time.sleep(minGuiDelay)
    pyautogui.click(addp(vbanWin.topleft, vbanOutAddr1))
    time.sleep(minGuiDelay)
    pyautogui.write(f"{addr}\n")
    time.sleep(minGuiDelay)
    pyautogui.click(addp(vbanWin.topleft, vbanOutPort1))
    time.sleep(minGuiDelay)
    pyautogui.write(f"{port}\n")
    time.sleep(minGuiDelay)
    img = pyautogui.screenshot()
    if img.getpixel(addp(vbanWin.topleft, vbanOutEnable1))[1] < 100:
        pyautogui.click(addp(vbanWin.topleft, vbanOutEnable1))


def vbanSetEnable(enable=True):
    logger.info(("en" if enable else "dis") + "abling vban")
    img = pyautogui.screenshot()
    if (img.getpixel(addp(vbanWin.topleft, vbanEnable))[1] > 200) != enable:
        pyautogui.click(addp(vbanWin.topleft, vbanEnable))


time.sleep(minGuiDelay)
pyautogui.click(addp(voicemeeterWin.topleft, vbanBtnPoint))
vbanWin = pyautogui.getAllWindows()[pyautogui.getAllTitles().index(vbanTitle)]
time.sleep(minGuiDelay)
if vbanWin.topleft.x < 0 or vbanWin.topleft.y < 0:
    pyautogui.moveTo(addp(vbanWin.topleft, vbanWinHeader))
    pyautogui.dragTo(310, 40, 0.3, button='left')

vbanSetEnable(False)


class Pinger(threading.Thread):
    def __init__(self, sentEvent=None):
        super(Pinger, self).__init__(name="Pinger")
        self.stop_it = threading.Event()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
        self.sock.bind(("0.0.0.0", 0))
        addr, self.inner_port = self.sock.getsockname()
        logger.info("pinger is bound to %s:%d", addr, self.inner_port)
        self.start()
        if sentEvent is not None:
            self.sent = sentEvent
        else:
            self.sent = threading.Event()

    def run(self):
        while not overall_timeout.is_set() or not self.stop_it.is_set():
            self.sock.sendto(b"p", (puncher_addr, puncher_vban_port))
            logger.info("pinged %s:%d", puncher_addr, puncher_vban_port)
            if not self.sent.is_set():
                self.sent.set()
            if overall_timeout.wait(10):
                break
        self.sock.close()
        if not self.stop_it.is_set():
            self.stop_it.set()
        logger.info("shutting down Pinger")


class Fetcher(threading.Thread):
    def __init__(self):
        super(Fetcher, self).__init__(name="Fetcher")
        logger.info("starting fetcher")
        self.stop_it = threading.Event()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
        self.sock.sendto(bytes(json.dumps({
            "punch_id": puncher_id,
            "clean": True
        }), "utf-8"), (puncher_addr, puncher_comm_port))
        self.sock.settimeout(3)
        self.continueEvent = threading.Event()
        self.start()
        self.my_info = None
        self.other_info = None

    def run(self):
        while not overall_timeout.is_set() and not self.continueEvent.is_set():
            self.continueEvent.wait(5)
        time.sleep(2)
        logger.info("sending get_my_ports request")
        self.sock.sendto(bytes(json.dumps({
            "punch_id": puncher_id,
            "get_my_ports": True
        }), "utf-8"), (puncher_addr, puncher_comm_port))
        count_ticks = 3
        while not self.stop_it.is_set() or not overall_timeout.is_set():
            count_ticks += 1
            if count_ticks > 3:
                count_ticks = 0
                logger.info("sending get_other_ports request")
                self.sock.sendto(bytes(json.dumps({
                    "punch_id": puncher_id,
                    "get_other_ports": True
                }), "utf-8"), (puncher_addr, puncher_comm_port))
            try:
                datastr, addr = self.sock.recvfrom(1500)
                data = json.loads(datastr)
            except socket.timeout:
                continue
            except json.JSONDecodeError:
                logger.warning("got unparseable data in server port from %s:%d\n%s", addr[0], addr[1], repr(datastr))
                continue

            if "comment" in data:
                if data["comment"] == "get_my_ports":
                    logger.info("got get_my_ports answer")
                    self.my_info = data
                    if "re_port" not in data:
                        logger.info("repeating get_my_ports request")
                        self.sock.sendto(bytes(json.dumps({
                            "punch_id": puncher_id,
                            "get_my_ports": True
                        }), "utf-8"), (puncher_addr, puncher_comm_port))
                if data["comment"] == "get_other_ports":
                    logger.info("got get_other_ports answer")
                    self.other_info = data
                    if "re_port" in data:
                        logger.info("got get_other_ports re_port, finalizing")
                        break
        if not self.stop_it.is_set():
            self.stop_it.set()
        self.sock.close()
        logger.info("shutting down Fetcher")


fetcher = Fetcher()
pinger = Pinger(fetcher.continueEvent)

fetcher.stop_it.wait()
pinger.stop_it.set()
pinger.join()

addr = socket.gethostbyname(fetcher.other_info["addr"])
vbanSetIn(addr, pinger.inner_port)
vbanSetOut(addr, fetcher.other_info["re_port"])
vbanSetEnable()

