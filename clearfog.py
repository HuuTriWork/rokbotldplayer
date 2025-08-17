import os
import time
import cv2
import subprocess
import threading
from rich.console import Console

ADB_PATH = "adb\\adb.exe"
DATA_PATH = "data"
SCREENSHOT_PATH = "cache\\screenshot.png"

console = Console()
stop_flag = False

def adb_screencap(device_id, output=SCREENSHOT_PATH):
    subprocess.run([ADB_PATH, "-s", device_id, "shell", "screencap", "-p", "/sdcard/screen.png"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run([ADB_PATH, "-s", device_id, "pull", "/sdcard/screen.png", output],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def adb_tap(device_id, x, y):
    subprocess.run([ADB_PATH, "-s", device_id, "shell", "input", "tap", str(x), str(y)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def find_image(target_path, screenshot_path=SCREENSHOT_PATH, threshold=0.85):
    if not os.path.exists(target_path):
        return None
    img_rgb = cv2.imread(screenshot_path)
    template = cv2.imread(target_path)
    if img_rgb is None or template is None:
        return None
    res = cv2.matchTemplate(img_rgb, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    if max_val >= threshold:
        cx = int(max_loc[0] + template.shape[1] / 2)
        cy = int(max_loc[1] + template.shape[0] / 2)
        return (cx, cy)
    return None

def wait_and_click(device_id, filename, must=True, delay=1, threshold=0.85):
    path = os.path.join(DATA_PATH, filename)
    while not stop_flag:
        adb_screencap(device_id)
        coord = find_image(path, threshold=threshold)
        if coord:
            adb_tap(device_id, *coord)
            time.sleep(delay)
            return True
        if not must:
            return False
        time.sleep(1)
    return False

def clear_fog(device_id):
    global stop_flag
    console.print("[cyan][🌸] ➜ Bắt Đầu Clear Fog (gõ 'stop' để dừng) 🌸[/cyan]")
    while not stop_flag:
        adb_screencap(device_id)
        if (coord := find_image(os.path.join(DATA_PATH, "home.png"))):
            adb_tap(device_id, *coord)
            time.sleep(2)
        elif (coord := find_image(os.path.join(DATA_PATH, "map.png"))):
            adb_tap(device_id, *coord)
            time.sleep(2)
            adb_screencap(device_id)
            if (coord2 := find_image(os.path.join(DATA_PATH, "home.png"))):
                adb_tap(device_id, *coord2)
                time.sleep(2)

        adb_screencap(device_id)
        target = None
        for i in range(1, 3):
            coord = find_image(os.path.join(DATA_PATH, f"{i}.png"))
            if coord:
                target = coord
                break
        if not target:
            continue
        adb_tap(device_id, *target)
        time.sleep(2)

        wait_and_click(device_id, "scout.png", must=False, delay=2)
        wait_and_click(device_id, "explore.png", must=True, delay=2)

        adb_screencap(device_id)
        if not find_image(os.path.join(DATA_PATH, "selected.png")):
            coord = find_image(os.path.join(DATA_PATH, "notselected.png"))
            if coord:
                adb_tap(device_id, *coord)
                time.sleep(1)

        wait_and_click(device_id, "explore.png", must=True, delay=3)
        wait_and_click(device_id, "send.png", must=True, delay=2)

    console.print("[red][🛑] ➜ Đã dừng![/red]")

def start_clear_fog(device_id):
    global stop_flag
    stop_flag = False
    def runner():
        clear_fog(device_id)
    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    while True:
        cmd = input().strip().lower()
        if cmd == "stop":
            stop_flag = True
            break
