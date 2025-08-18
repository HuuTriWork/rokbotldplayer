import os
import sys
import subprocess
import threading
import time
import re
import cv2
import pytesseract
from rich.console import Console
from rich.table import Table
from rich import box
import PySimpleGUI as sg

ADB_PATH = "adb\\adb.exe"
DATA_PATH = "data"
SCREENSHOT_PATH = "cache\\screenshot.png"
TESSERACT_PATH = r"tesseract-ocr\\tesseract.exe"

console = Console()
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
connected_devices = set()
stop_gather_flag = False
stop_clear_fog_flag = False

def get_ldplayer_devices():
    result = subprocess.run([ADB_PATH, "devices"], capture_output=True, text=True)
    lines = result.stdout.strip().splitlines()[1:]
    devices = []
    for line in lines:
        if not line.strip():
            continue
        parts = line.split()
        device_id = parts[0]
        if device_id.startswith("emulator-"):
            devices.append(device_id)
    return devices

def list_devices():
    devices = get_ldplayer_devices()
    data = []
    for dev in devices:
        status = "online" if dev in connected_devices else "offline"
        data.append((dev, status))
    return data

def connect_devices(selection, devices):
    targets = []
    if selection.lower() == "all":
        targets = [d[0] for d in devices]
    else:
        for idx in selection.split(","):
            idx = idx.strip()
            if idx.isdigit() and 1 <= int(idx) <= len(devices):
                targets.append(devices[int(idx)-1][0])

    results = []
    for dev in targets:
        port_num = int(dev.split("-")[-1]) + 1
        ip_port = f"127.0.0.1:{port_num}"
        result = subprocess.run([ADB_PATH, "connect", ip_port], capture_output=True, text=True)
        if "connected" in result.stdout.lower() or "already" in result.stdout.lower():
            connected_devices.add(dev)
            results.append((dev, True, "Connected"))
        else:
            results.append((dev, False, result.stdout.strip()))
    return results

def disconnect_devices(selection, devices):
    targets = []
    if selection.lower() == "all":
        targets = [d[0] for d in devices]
    else:
        for idx in selection.split(","):
            idx = idx.strip()
            if idx.isdigit() and 1 <= int(idx) <= len(devices):
                targets.append(devices[int(idx)-1][0])

    results = []
    for dev in targets:
        port_num = int(dev.split("-")[-1]) + 1
        ip_port = f"127.0.0.1:{port_num}"
        subprocess.run([ADB_PATH, "disconnect", ip_port],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        connected_devices.discard(dev)
        results.append((dev, True, "Disconnected"))
    return results

def launch_game(selection, devices, package_name):
    online_devices = [d for d in devices if d[1] == "online"]
    if not online_devices:
        return "No online devices available to launch game"

    targets = []
    if selection.lower() == "all":
        targets = [d[0] for d in online_devices]
    else:
        for idx in selection.split(","):
            idx = idx.strip()
            if idx.isdigit() and 1 <= int(idx) <= len(devices):
                dev_id, status = devices[int(idx)-1]
                if status == "online":
                    targets.append(dev_id)

    for dev in targets:
        subprocess.run([ADB_PATH, "-s", dev, "shell", "monkey",
                       "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1"],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return f"Launched {package_name} on {len(targets)} devices"

def close_game(selection, devices, package_name):
    online_devices = [d for d in devices if d[1] == "online"]
    if not online_devices:
        return "No online devices available to close game"

    targets = []
    if selection.lower() == "all":
        targets = [d[0] for d in online_devices]
    else:
        for idx in selection.split(","):
            idx = idx.strip()
            if idx.isdigit() and 1 <= int(idx) <= len(devices):
                dev_id, status = devices[int(idx)-1]
                if status == "online":
                    targets.append(dev_id)

    for dev in targets:
        subprocess.run([ADB_PATH, "-s", dev, "shell", "am", "force-stop", package_name],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return f"Closed {package_name} on {len(targets)} devices"

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
        center_x = int(max_loc[0] + template.shape[1] / 2)
        center_y = int(max_loc[1] + template.shape[0] / 2)
        return (center_x, center_y)
    return None

def convert_to_number(text):
    if not text:
        return 0
    text = text.upper().replace(" ", "").replace(",", "")
    match = re.match(r"(\d+(\.\d+)?)([KMB]?)", text)
    if not match:
        return 0
    num = float(match.group(1))
    suffix = match.group(3)
    if suffix == "K":
        num *= 1_000
    elif suffix == "M":
        num *= 1_000_000
    elif suffix == "B":
        num *= 1_000_000_000
    return int(num)

def ocr_resources_auto(image_path):
    img = cv2.imread(image_path)
    h, w, _ = img.shape
    x1, x2 = int(w * 0.63), int(w * 0.92)
    start_y = int(h * 0.33)
    row_height = int(h * 0.095)
    crops = {}
    keys = ["Food", "Wood", "Stone", "Gold"]
    for i, key in enumerate(keys):
        y1 = start_y + i * row_height
        y2 = y1 + row_height
        crop = img[y1:y2, x1:x2]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        _, thresh = cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY)
        text = pytesseract.image_to_string(
            thresh,
            config="--psm 7 -c tessedit_char_whitelist=0123456789.,KMB"
        ).strip()
        match = re.search(r"[\d,]+(\.\d+)?[KMB]?", text)
        value = match.group(0) if match else text
        crops[key] = value
    return crops

def handle_disconnect(device_id, paths):
    global stop_gather_flag
    if stop_gather_flag:
        return False
    
    adb_screencap(device_id)
    
    if find_image(paths["disconnect"], screenshot_path=SCREENSHOT_PATH, threshold=0.9):
        confirm_coord = find_image(paths["confirm"], screenshot_path=SCREENSHOT_PATH)
        if confirm_coord:
            adb_tap(device_id, *confirm_coord)
            time.sleep(30)
        else:
            time.sleep(30)
    return True

def gather_rss_thread(device_id, window, max_marches=6):
    global stop_gather_flag
    stop_gather_flag = False
    
    paths = {name: os.path.join(DATA_PATH, f"{name}.png") for name in
             ["home", "map", "item", "task", "info", "exit", "find",
              "food", "wood", "stone", "gold", "up", "down",
              "search", "gather", "newtroop", "march",
              "disconnect", "confirm"]} 

    window.write_event_value('-GATHER-LOG-', "🌸 Bắt Đầu Thu Thập Tài Nguyên 🌸")
    
    if not handle_disconnect(device_id, paths):
        return
    
    adb_screencap(device_id)
    if home_coord := find_image(paths["home"], threshold=0.9):
        window.write_event_value('-GATHER-LOG-', "Đang trở về thành phố...")
        adb_tap(device_id, *home_coord)
        time.sleep(5)
    else:
        window.write_event_value('-GATHER-LOG-', "Đã ở trong thành phố.")
    
    time.sleep(5)
    if not handle_disconnect(device_id, paths):
        return
    
    adb_screencap(device_id)
    window.write_event_value('-GATHER-LOG-', "Đang mở túi đồ...")
    item_coord = find_image(paths["item"])
    if not item_coord:
        window.write_event_value('-GATHER-LOG-', "Không tìm thấy túi đồ, đang mở task và thử lại...")
        if task_coord := find_image(paths["task"]):
            adb_tap(device_id, *task_coord)
            time.sleep(5)
            if not handle_disconnect(device_id, paths):
                return
            adb_screencap(device_id)
            item_coord = find_image(paths["item"])
        if not item_coord:
            window.write_event_value('-GATHER-LOG-', "Không thể mở túi đồ!")
            return
    
    adb_tap(device_id, *item_coord)
    time.sleep(5)
    
    if not handle_disconnect(device_id, paths):
        return
    
    adb_screencap(device_id)
    window.write_event_value('-GATHER-LOG-', "Đang mở bảng tài nguyên...")
    if info_coord := find_image(paths["info"]):
        adb_tap(device_id, *info_coord)
        time.sleep(5)
    else:
        window.write_event_value('-GATHER-LOG-', "Không tìm thấy nút thông tin!")
        return

    window.write_event_value('-GATHER-LOG-', "Đang đọc số liệu tài nguyên...")
    if not handle_disconnect(device_id, paths):
        return
    
    adb_screencap(device_id)
    resources = ocr_resources_auto(SCREENSHOT_PATH)
    window.write_event_value('-GATHER-LOG-', f"Tài nguyên: {resources}")
    numeric_resources = {k: convert_to_number(v) for k, v in resources.items()}
    sorted_res = sorted(numeric_resources.items(), key=lambda x: x[1])

    window.write_event_value('-GATHER-LOG-', "Đang trở về bản đồ...")
    for _ in range(2):
        if not handle_disconnect(device_id, paths):
            return
        if exit_coord := find_image(paths["exit"]):
            adb_tap(device_id, *exit_coord)
            time.sleep(2)
            adb_screencap(device_id)
    
    if map_coord := find_image(paths["map"]):
        adb_tap(device_id, *map_coord)
    time.sleep(5)

    count = 0
    while count < max_marches and not stop_gather_flag:
        res_name, res_value = sorted_res[count % len(sorted_res)]
        if res_value == 0:
            window.write_event_value('-GATHER-LOG-', f"Không tìm thấy {res_name}, bỏ qua...")
            count += 1
            continue

        window.write_event_value('-GATHER-LOG-', f"Đạo quân {count + 1}/{max_marches} | Thu thập {res_name}")
        
        if not handle_disconnect(device_id, paths):
            return
        
        adb_screencap(device_id)
        if not (find_coord := find_image(paths["find"])):
            window.write_event_value('-GATHER-LOG-', "Không tìm thấy nút tìm kiếm!")
            return
        adb_tap(device_id, *find_coord)
        time.sleep(5)

        window.write_event_value('-GATHER-LOG-', f"Chọn {res_name}...")
        if not handle_disconnect(device_id, paths):
            return
        
        adb_screencap(device_id)
        if not (res_coord := find_image(paths[res_name.lower()])):
            window.write_event_value('-GATHER-LOG-', f"Không tìm thấy {res_name}!")
            return
        adb_tap(device_id, *res_coord)
        time.sleep(5)

        window.write_event_value('-GATHER-LOG-', "Đang tăng level mỏ...")
        for _ in range(6):
            if not handle_disconnect(device_id, paths):
                return
            adb_screencap(device_id)
            if up_coord := find_image(paths["up"]):
                adb_tap(device_id, *up_coord)
                time.sleep(0.25)

        window.write_event_value('-GATHER-LOG-', "Đang tìm mỏ...")
        if not handle_disconnect(device_id, paths):
            return
        
        adb_screencap(device_id)
        if not (search_coord := find_image(paths["search"])):
            window.write_event_value('-GATHER-LOG-', "Không thấy nút tìm mỏ!")
            return
        adb_tap(device_id, *search_coord)
        
        found_gather = False
        max_attempts = 6
        for attempt in range(max_attempts):
            if stop_gather_flag:
                window.write_event_value('-GATHER-LOG-', "Đã dừng thu thập tài nguyên!")
                return
                
            time.sleep(5)
            if not handle_disconnect(device_id, paths):
                return
            
            adb_screencap(device_id)
            if gather_coord := find_image(paths["gather"]):
                adb_tap(device_id, *gather_coord)
                found_gather = True
                window.write_event_value('-GATHER-LOG-', "Tìm thấy mỏ, tiến hành thu thập...")
                break
            else:
                window.write_event_value('-GATHER-LOG-', f"Đang giảm level mỏ và tìm lại... ({attempt + 2}/{max_attempts})")
                if down_coord := find_image(paths["down"]):
                    adb_tap(device_id, *down_coord)
                    time.sleep(0.25)
                
                if not handle_disconnect(device_id, paths):
                    return
                
                adb_screencap(device_id)
                if search_coord := find_image(paths["search"]):
                    adb_tap(device_id, *search_coord)
                else:
                    window.write_event_value('-GATHER-LOG-', "Không tìm thấy nút tìm mỏ để thử lại!")
                    break
    
        if found_gather:
            window.write_event_value('-GATHER-LOG-', "Đang kiểm tra đạo quân...")
            time.sleep(5)
            if not handle_disconnect(device_id, paths):
                return
            
            adb_screencap(device_id)
            if newtroop_coord := find_image(paths["newtroop"]):
                window.write_event_value('-GATHER-LOG-', "Còn đạo quân, tiến hành gửi quân đi thu thập...")
                adb_tap(device_id, *newtroop_coord)
                time.sleep(5)

                if not handle_disconnect(device_id, paths):
                    return
                
                adb_screencap(device_id)
                if march_coord := find_image(paths["march"]):
                    adb_tap(device_id, *march_coord)
                    window.write_event_value('-GATHER-LOG-', "Đã gửi quân đi thu thập!")
                    time.sleep(5)
                    count += 1
                else:
                    window.write_event_value('-GATHER-LOG-', "Không thể gửi quân!")
                    return
            else:
                window.write_event_value('-GATHER-LOG-', "Hết đạo quân trống. Kết thúc!")
                return
        else:
            window.write_event_value('-GATHER-LOG-', f"Không tìm thấy mỏ {res_name}, chuyển sang lượt sau...")
            count += 1

    if count >= max_marches:
        window.write_event_value('-GATHER-LOG-', f"Đã gửi đủ {max_marches} đạo quân. Hoàn thành!")
    else:
        window.write_event_value('-GATHER-LOG-', "Đã dừng thu thập tài nguyên!")

def clear_fog_thread(device_id, window):
    global stop_clear_fog_flag
    stop_clear_fog_flag = False
    
    templates = {}
    for file in os.listdir(DATA_PATH):
        path = os.path.join(DATA_PATH, file)
        if file.endswith(".png") and os.path.isfile(path):
            templates[file] = cv2.imread(path)

    def adb_screencap(device_id, output=SCREENSHOT_PATH):
        with open(output, "wb") as f:
            subprocess.run(
                [ADB_PATH, "-s", device_id, "exec-out", "screencap", "-p"],
                stdout=f, stderr=subprocess.DEVNULL
            )

    def adb_tap(device_id, x, y):
        subprocess.run(
            [ADB_PATH, "-s", device_id, "shell", "input", "tap", str(x), str(y)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

    def find_image(filename, screenshot_path=SCREENSHOT_PATH, threshold=0.85):
        if filename not in templates:
            return None
        img_rgb = cv2.imread(screenshot_path)
        template = templates[filename]
        if img_rgb is None or template is None:
            return None
        res = cv2.matchTemplate(img_rgb, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        if max_val >= threshold:
            cx = int(max_loc[0] + template.shape[1] / 2)
            cy = int(max_loc[1] + template.shape[0] / 2)
            return (cx, cy)
        return None

    def wait_and_click(filename, must=True, delay=1, threshold=0.85):
        nonlocal device_id
        while not stop_clear_fog_flag:
            adb_screencap(device_id)
            coord = find_image(filename, threshold=threshold)
            if coord:
                adb_tap(device_id, *coord)
                time.sleep(delay)
                return True
            if not must:
                return False
            time.sleep(0.3)
        return False

    window.write_event_value('-CLEARFOG-LOG-', "🌸 Bắt Đầu Clear Fog 🌸")

    while not stop_clear_fog_flag:
        adb_screencap(device_id)
        if (coord := find_image("home.png")):
            adb_tap(device_id, *coord); time.sleep(1.5)
        elif (coord := find_image("map.png")):
            adb_tap(device_id, *coord); time.sleep(1.5)
            adb_screencap(device_id)
            if (coord2 := find_image("home.png")):
                adb_tap(device_id, *coord2); time.sleep(1.5)

        adb_screencap(device_id)
        target = None
        for i in range(1, 4):
            coord = find_image(f"{i}.png")
            if coord:
                target = coord; break
        if not target:
            continue

        adb_tap(device_id, *target); time.sleep(1.5)
        wait_and_click("scout.png", must=False, delay=1.5)
        wait_and_click("explore.png", must=True, delay=1.5)

        adb_screencap(device_id)
        if not find_image("selected.png"):
            if (coord := find_image("notselected.png")):
                adb_tap(device_id, *coord); time.sleep(0.8)

        wait_and_click("explore.png", must=True, delay=2)
        wait_and_click("send.png", must=True, delay=1.5)

    window.write_event_value('-CLEARFOG-LOG-', "🛑 Đã dừng Clear Fog!")

def create_main_window():
    sg.theme('DarkAmber')
    
    device_list_column = [
        [sg.Text('Danh sách thiết bị:', font=('Helvetica', 12, 'bold'))],
        [sg.Multiline(size=(60, 10), key='-DEVICE-LIST-', disabled=True, autoscroll=True)],
        [sg.Button('Làm mới', key='-REFRESH-DEVICES-'), 
         sg.Button('Kết nối', key='-CONNECT-DEVICES-'), 
         sg.Button('Ngắt kết nối', key='-DISCONNECT-DEVICES-')]
    ]
    
    game_control_column = [
        [sg.Text('Điều khiển trò chơi:', font=('Helvetica', 12, 'bold'))],
        [sg.Radio('Global', "GAME_VERSION", default=True, key='-GLOBAL-'), 
         sg.Radio('VN', "GAME_VERSION", key='-VN-')],
        [sg.Button('Khởi động game', key='-LAUNCH-GAME-'), 
         sg.Button('Đóng game', key='-CLOSE-GAME-')]
    ]
    
    gather_rss_column = [
        [sg.Text('Thu thập tài nguyên:', font=('Helvetica', 12, 'bold'))],
        [sg.Text('Số đạo quân:'), sg.Input('6', size=(5, 1), key='-MARCHES-')],
        [sg.Button('Bắt đầu', key='-START-GATHER-'), 
         sg.Button('Dừng', key='-STOP-GATHER-', disabled=True)],
        [sg.Multiline(size=(60, 10), key='-GATHER-LOG-', disabled=True, autoscroll=True)]
    ]
    
    clear_fog_column = [
        [sg.Text('Clear Fog:', font=('Helvetica', 12, 'bold'))],
        [sg.Button('Bắt đầu', key='-START-CLEARFOG-'), 
         sg.Button('Dừng', key='-STOP-CLEARFOG-', disabled=True)],
        [sg.Multiline(size=(60, 10), key='-CLEARFOG-LOG-', disabled=True, autoscroll=True)]
    ]
    
    layout = [
        [sg.Column(device_list_column), sg.VSeparator(), sg.Column(game_control_column)],
        [sg.HSeparator()],
        [sg.Column(gather_rss_column), sg.VSeparator(), sg.Column(clear_fog_column)]
    ]
    
    return sg.Window('ROK Tool 2025', layout, finalize=True, resizable=True)

def update_device_list(window):
    devices = list_devices()
    text = ""
    if not devices:
        text = "Không tìm thấy thiết bị nào!"
    else:
        for i, (device, status) in enumerate(devices, start=1):
            icon = "🟢" if status == "online" else "🔴"
            text += f"{i}. {device} - {icon} {status}\n"
    window['-DEVICE-LIST-'].update(text)

def main():
    window = create_main_window()
    gather_thread = None
    clear_fog_thread_obj = None
    
    while True:
        event, values = window.read()
        
        if event == sg.WINDOW_CLOSED:
            break
            
        elif event == '-REFRESH-DEVICES-':
            update_device_list(window)
            
        elif event == '-CONNECT-DEVICES-':
            devices = list_devices()
            if not devices:
                sg.popup("Không tìm thấy thiết bị nào!")
                continue
                
            layout = [
                [sg.Text('Chọn thiết bị để kết nối:')],
                [sg.Listbox([f"{i}. {d[0]} - {d[1]}" for i, d in enumerate(devices, 1)], 
                          size=(50, min(10, len(devices))), key='-DEVICE-SELECTION-')],
                [sg.Radio('Tất cả', "CONNECT_OPTION", default=True, key='-ALL-'),
                 sg.Radio('Chọn thủ công', "CONNECT_OPTION", key='-MANUAL-')],
                [sg.Button('Kết nối'), sg.Button('Hủy')]
            ]
            
            connect_window = sg.Window('Kết nối thiết bị', layout, modal=True)
            while True:
                connect_event, connect_values = connect_window.read()
                if connect_event in (sg.WINDOW_CLOSED, 'Hủy'):
                    break
                elif connect_event == 'Kết nối':
                    if connect_values['-ALL-']:
                        selection = "all"
                    else:
                        selected = connect_values['-DEVICE-SELECTION-']
                        if not selected:
                            sg.popup("Vui lòng chọn ít nhất một thiết bị!")
                            continue
                        indices = [int(s.split('.')[0]) for s in selected]
                        selection = ",".join(map(str, indices))
                    
                    results = connect_devices(selection, devices)
                    for did, ok, msg in results:
                        color = "green" if ok else "red"
                        sg.popup(f"{did}: {msg}", title="Kết quả kết nối", text_color=color)
                    update_device_list(window)
                    break
            connect_window.close()
            
        elif event == '-DISCONNECT-DEVICES-':
            devices = list_devices()
            if not devices:
                sg.popup("Không tìm thấy thiết bị nào!")
                continue
                
            layout = [
                [sg.Text('Chọn thiết bị để ngắt kết nối:')],
                [sg.Listbox([f"{i}. {d[0]} - {d[1]}" for i, d in enumerate(devices, 1)], 
                          size=(50, min(10, len(devices))), key='-DEVICE-SELECTION-')],
                [sg.Radio('Tất cả', "DISCONNECT_OPTION", default=True, key='-ALL-'),
                 sg.Radio('Chọn thủ công', "DISCONNECT_OPTION", key='-MANUAL-')],
                [sg.Button('Ngắt kết nối'), sg.Button('Hủy')]
            ]
            
            disconnect_window = sg.Window('Ngắt kết nối thiết bị', layout, modal=True)
            while True:
                disconnect_event, disconnect_values = disconnect_window.read()
                if disconnect_event in (sg.WINDOW_CLOSED, 'Hủy'):
                    break
                elif disconnect_event == 'Ngắt kết nối':
                    if disconnect_values['-ALL-']:
                        selection = "all"
                    else:
                        selected = disconnect_values['-DEVICE-SELECTION-']
                        if not selected:
                            sg.popup("Vui lòng chọn ít nhất một thiết bị!")
                            continue
                        indices = [int(s.split('.')[0]) for s in selected]
                        selection = ",".join(map(str, indices))
                    
                    results = disconnect_devices(selection, devices)
                    for did, ok, msg in results:
                        sg.popup(f"{did}: {msg}", title="Kết quả ngắt kết nối")
                    update_device_list(window)
                    break
            disconnect_window.close()
            
        elif event == '-LAUNCH-GAME-':
            devices = list_devices()
            if not devices:
                sg.popup("Không tìm thấy thiết bị nào!")
                continue
                
            package_name = "com.lilithgame.roc.gp" if values['-GLOBAL-'] else "com.rok.gp.vn"
            result = launch_game("all", devices, package_name)
            sg.popup(result)
            
        elif event == '-CLOSE-GAME-':
            devices = list_devices()
            if not devices:
                sg.popup("Không tìm thấy thiết bị nào!")
                continue
                
            package_name = "com.lilithgame.roc.gp" if values['-GLOBAL-'] else "com.rok.gp.vn"
            result = close_game("all", devices, package_name)
            sg.popup(result)
            
        elif event == '-START-GATHER-':
            devices = list_devices()
            online_devices = [d for d in devices if d[1] == "online"]
            if not online_devices:
                sg.popup("Không có thiết bị nào đang online!")
                continue
                
            try:
                max_marches = int(values['-MARCHES-'])
                if max_marches <= 0:
                    raise ValueError
            except ValueError:
                sg.popup("Vui lòng nhập số đạo quân hợp lệ (số nguyên dương)!")
                continue
                
            if len(online_devices) > 1:
                layout = [
                    [sg.Text('Chọn thiết bị để thu thập tài nguyên:')],
                    [sg.Listbox([f"{i}. {d[0]}" for i, d in enumerate(online_devices, 1)], 
                              size=(50, min(10, len(online_devices))), key='-DEVICE-SELECTION-')],
                    [sg.Button('Bắt đầu'), sg.Button('Hủy')]
                ]
                
                select_window = sg.Window('Chọn thiết bị', layout, modal=True)
                while True:
                    select_event, select_values = select_window.read()
                    if select_event in (sg.WINDOW_CLOSED, 'Hủy'):
                        break
                    elif select_event == 'Bắt đầu':
                        selected = select_values['-DEVICE-SELECTION-']
                        if not selected:
                            sg.popup("Vui lòng chọn ít nhất một thiết bị!")
                            continue
                        device_idx = int(selected[0].split('.')[0]) - 1
                        device_id = online_devices[device_idx][0]
                        
                        window['-START-GATHER-'].update(disabled=True)
                        window['-STOP-GATHER-'].update(disabled=False)
                        window['-GATHER-LOG-'].update("")
                        
                        gather_thread = threading.Thread(
                            target=gather_rss_thread,
                            args=(device_id, window, max_marches),
                            daemon=True
                        )
                        gather_thread.start()
                        break
                select_window.close()
            else:
                device_id = online_devices[0][0]
                window['-START-GATHER-'].update(disabled=True)
                window['-STOP-GATHER-'].update(disabled=False)
                window['-GATHER-LOG-'].update("")
                
                gather_thread = threading.Thread(
                    target=gather_rss_thread,
                    args=(device_id, window, max_marches),
                    daemon=True
                )
                gather_thread.start()
                
        elif event == '-STOP-GATHER-':
            global stop_gather_flag
            stop_gather_flag = True
            window['-STOP-GATHER-'].update(disabled=True)
            window['-START-GATHER-'].update(disabled=False)
            
        elif event == '-GATHER-LOG-':
            window['-GATHER-LOG-'].print(values[event])
            
        elif event == '-START-CLEARFOG-':
            devices = list_devices()
            online_devices = [d for d in devices if d[1] == "online"]
            if not online_devices:
                sg.popup("Không có thiết bị nào đang online!")
                continue
                
            if len(online_devices) > 1:
                layout = [
                    [sg.Text('Chọn thiết bị để Clear Fog:')],
                    [sg.Listbox([f"{i}. {d[0]}" for i, d in enumerate(online_devices, 1)], 
                              size=(50, min(10, len(online_devices))), key='-DEVICE-SELECTION-')],
                    [sg.Button('Bắt đầu'), sg.Button('Hủy')]
                ]
                
                select_window = sg.Window('Chọn thiết bị', layout, modal=True)
                while True:
                    select_event, select_values = select_window.read()
                    if select_event in (sg.WINDOW_CLOSED, 'Hủy'):
                        break
                    elif select_event == 'Bắt đầu':
                        selected = select_values['-DEVICE-SELECTION-']
                        if not selected:
                            sg.popup("Vui lòng chọn ít nhất một thiết bị!")
                            continue
                        device_idx = int(selected[0].split('.')[0]) - 1
                        device_id = online_devices[device_idx][0]
                        
                        window['-START-CLEARFOG-'].update(disabled=True)
                        window['-STOP-CLEARFOG-'].update(disabled=False)
                        window['-CLEARFOG-LOG-'].update("")
                        
                        clear_fog_thread_obj = threading.Thread(
                            target=clear_fog_thread,
                            args=(device_id, window),
                            daemon=True
                        )
                        clear_fog_thread_obj.start()
                        break
                select_window.close()
            else:
                device_id = online_devices[0][0]
                window['-START-CLEARFOG-'].update(disabled=True)
                window['-STOP-CLEARFOG-'].update(disabled=False)
                window['-CLEARFOG-LOG-'].update("")
                
                clear_fog_thread_obj = threading.Thread(
                    target=clear_fog_thread,
                    args=(device_id, window),
                    daemon=True
                )
                clear_fog_thread_obj.start()
                
        elif event == '-STOP-CLEARFOG-':
            global stop_clear_fog_flag
            stop_clear_fog_flag = True
            window['-STOP-CLEARFOG-'].update(disabled=True)
            window['-START-CLEARFOG-'].update(disabled=False)
            
        elif event == '-CLEARFOG-LOG-':
            window['-CLEARFOG-LOG-'].print(values[event])
    
    window.close()

if __name__ == "__main__":
    REQUIRED_MODULES = ["rich", "pytesseract", "numpy", "opencv-python", "PySimpleGUI"]
    
    for module in REQUIRED_MODULES:
        try:
            __import__(module.split("-")[0])
        except ImportError:
            print(f"[⚠️] ➜ Module '{module}' chưa có. Đang cài đặt...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", module])
    
    main()