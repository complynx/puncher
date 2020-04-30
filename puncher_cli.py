import time
import socket
import sys
import json

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
    img = pyautogui.screenshot()
    if (img.getpixel(addp(vbanWin.topleft, vbanEnable))[1] < 200) != enable:
        pyautogui.click(addp(vbanWin.topleft, vbanEnable))


time.sleep(minGuiDelay)
pyautogui.click(addp(voicemeeterWin.topleft, vbanBtnPoint))
vbanWin = pyautogui.getAllWindows()[pyautogui.getAllTitles().index(vbanTitle)]
time.sleep(minGuiDelay)
if vbanWin.topleft.x < 0 or vbanWin.topleft.y < 0:
    pyautogui.moveTo(addp(vbanWin.topleft, vbanWinHeader))
    pyautogui.dragTo(310, 40, 0.3, button='left')

vbanSetEnable(False)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
sock.sendto(bytes(json.dumps({
    "punch_id": puncher_id
}), "utf-8"), (puncher_addr, puncher_comm_port))

sockpunch = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sockpunch.bind(("0.0.0.0", puncher_vban_port))
sockpunch.sendto(b"p", (puncher_addr, puncher_vban_port))
sockpunch.close()

sock.sendto(bytes(json.dumps({
    "punch_id": puncher_id,
    "set_send_to": True
}), "utf-8"), (puncher_addr, puncher_comm_port))

vbanSetIn(puncher_addr, puncher_vban_port)
vbanSetOut(puncher_addr, puncher_vban_port)
vbanSetEnable()

sock.close()
