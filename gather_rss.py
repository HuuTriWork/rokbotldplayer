import os
import re
import cv2
import time
import subprocess
import pytesseract
from rich.console import Console

ADB_PATH = "adb\\adb.exe"
DATA_PATH = "data"
SCREENSHOT_PATH = "cache\\screenshot.png"
TESSERACT_PATH = r"tesseract-ocr\\tesseract.exe"

console = Console()
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

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
    adb_screencap(device_id)
    
    if find_image(paths["disconnect"], screenshot_path=SCREENSHOT_PATH, threshold=0.9):
        console.print("[bold red][🔴] ➜ Phát hiện mất kết nối! Đang xử lý...[/bold red]")
        
        confirm_coord = find_image(paths["confirm"], screenshot_path=SCREENSHOT_PATH)
        if confirm_coord:
            console.print("[⚜️] ➜ Đang kết nối lại...")
            adb_tap(device_id, *confirm_coord)
            console.print("[⚜️] ➜ Đợi 30 giây để trò chơi tải lại...")
            time.sleep(30)
            console.print("[bold green][✅] ➜ Xử lý hoàn tất. Tiếp tục công việc...[/bold green]")
        else:
            console.print("[bold red][⚠️] ➜ Không tìm thấy nút kết nối lại![/bold red]")
            time.sleep(30)

def gather_rss(device_id, sorted_res=None, count=0, max_marches=6):
    paths = {name: os.path.join(DATA_PATH, f"{name}.png") for name in
             ["home", "map", "item", "task", "info", "exit", "find",
              "food", "wood", "stone", "gold", "up", "down",
              "search", "gather", "newtroop", "march",
              "disconnect", "confirm"]} 

    if sorted_res is None:
        console.print("[bold yellow]🌸 Bắt Đầu Thu Thập Tài Nguyên 🌸[/bold yellow]")
        handle_disconnect(device_id, paths)
        adb_screencap(device_id)
        if home_coord := find_image(paths["home"], threshold=0.9):
            console.print("[⚜️] ➜ Đang trở về thành phố...")
            adb_tap(device_id, *home_coord)
            time.sleep(5)
        else:
            console.print("[⚜️] ➜ Đã ở trong thành phố.")
        
        time.sleep(5)
        handle_disconnect(device_id, paths)
        adb_screencap(device_id)
        
        console.print("[⚜️] ➜ Đang mở túi đồ...")
        item_coord = find_image(paths["item"])
        if not item_coord:
            console.print("[⚠️] ➜ Không tìm thấy túi đồ, đang mở task và thử lại...")
            if task_coord := find_image(paths["task"]):
                adb_tap(device_id, *task_coord)
                time.sleep(5)
                handle_disconnect(device_id, paths)
                adb_screencap(device_id)
                item_coord = find_image(paths["item"])
            if not item_coord:
                console.print("[red][⚠️] ➜ Không thể mở túi đồ![/red]")
                return
        adb_tap(device_id, *item_coord)
        time.sleep(5)
        
        handle_disconnect(device_id, paths)
        adb_screencap(device_id)
        console.print("[⚜️] ➜ Đang mở bảng tài nguyên...")
        if info_coord := find_image(paths["info"]):
            adb_tap(device_id, *info_coord)
            time.sleep(5)
        else:
            console.print("[red][⚠️] ➜ Không tìm thấy nút thông tin![/red]")
            return

        console.print("[⚜️] ➜ Đang đọc số liệu tài nguyên...")
        handle_disconnect(device_id, paths)
        adb_screencap(device_id)
        resources = ocr_resources_auto(SCREENSHOT_PATH)
        console.print(f"[⚜️] ➜ Tài nguyên: {resources}")
        numeric_resources = {k: convert_to_number(v) for k, v in resources.items()}
        sorted_res = sorted(numeric_resources.items(), key=lambda x: x[1])

        console.print("[⚜️] ➜ Đang trở về bản đồ...")
        for _ in range(2):
            handle_disconnect(device_id, paths) 
            if exit_coord := find_image(paths["exit"]):
                adb_tap(device_id, *exit_coord)
                time.sleep(2)
                adb_screencap(device_id)
        
        if map_coord := find_image(paths["map"]):
            adb_tap(device_id, *map_coord)
        time.sleep(5)

    if count >= max_marches:
        console.print(f"[bold green][✅] ➜ Đã gửi đủ {max_marches} đạo quân. Hoàn thành![/bold green]")
        return

    res_name, res_value = sorted_res[count % len(sorted_res)]
    if res_value == 0:
        console.print(f"[⚜️] ➜ Không tìm thấy {res_name}, bỏ qua...")
        return gather_rss(device_id, sorted_res, count + 1, max_marches)

    console.print(f"[⚜️] ➜ Đạo quân {count + 1}/{max_marches} | Thu thập [bold]{res_name}[/bold]")
    
    handle_disconnect(device_id, paths)
    adb_screencap(device_id)
    if not (find_coord := find_image(paths["find"])):
        console.print("[red][⚠️] ➜ Không tìm thấy nút tìm kiếm![/red]")
        return
    adb_tap(device_id, *find_coord)
    time.sleep(5)

    console.print(f"➡️ Chọn {res_name}...")
    handle_disconnect(device_id, paths)
    adb_screencap(device_id)
    if not (res_coord := find_image(paths[res_name.lower()])):
        console.print(f"[red][⚠️] ➜ Không tìm thấy {res_name}![/red]")
        return
    adb_tap(device_id, *res_coord)
    time.sleep(5)

    console.print("[⚜️] ➜ Đang tăng level mỏ...")
    for _ in range(6):
        handle_disconnect(device_id, paths)
        adb_screencap(device_id)
        if up_coord := find_image(paths["up"]):
            adb_tap(device_id, *up_coord)
            time.sleep(0.25)

    console.print("[⚜️] ➜ Đang tìm mỏ...")
    handle_disconnect(device_id, paths)
    adb_screencap(device_id)
    if not (search_coord := find_image(paths["search"])):
        console.print("[red][⚠️] ➜ Không thấy nút tìm mỏ![/red]")
        return
    adb_tap(device_id, *search_coord)
    
    found_gather = False
    max_attempts = 6
    for attempt in range(max_attempts):
        time.sleep(5)
        handle_disconnect(device_id, paths)
        adb_screencap(device_id)
        if gather_coord := find_image(paths["gather"]):
            adb_tap(device_id, *gather_coord)
            found_gather = True
            console.print("[green][⚜️] ➜ Tìm thấy mỏ, tiến hành thu thập...[/green]")
            break
        else:
            console.print(f"[⚜️] ➜ Đang giảm level mỏ và tìm lại... ({attempt + 2}/{max_attempts})")
            if down_coord := find_image(paths["down"]):
                adb_tap(device_id, *down_coord)
                time.sleep(0.25)
            
            handle_disconnect(device_id, paths) 
            adb_screencap(device_id)
            if search_coord := find_image(paths["search"]):
                adb_tap(device_id, *search_coord)
            else:
                console.print("[red][⚠️] ➜ Không tìm thấy nút tìm mỏ để thử lại![/red]")
                break
    
    if found_gather:
        console.print("[⚜️] ➜ Đang kiểm tra đạo quân...")
        time.sleep(5)
        handle_disconnect(device_id, paths)
        adb_screencap(device_id)
        if newtroop_coord := find_image(paths["newtroop"]):
            console.print("[⚜️] ➜ Còn đạo quân, tiến hành gửi quân đi thu thập...")
            adb_tap(device_id, *newtroop_coord)
            time.sleep(5)

            handle_disconnect(device_id, paths)
            adb_screencap(device_id)
            if march_coord := find_image(paths["march"]):
                adb_tap(device_id, *march_coord)
                console.print("[green][⚜️] ➜ Đã gửi quân đi thu thập![/green]")
                time.sleep(5)
                return gather_rss(device_id, sorted_res, count + 1, max_marches)
            else:
                console.print("[red][⚠️] ➜ Không thể gửi quân![/red]")
                return
        else:
            console.print("[bold red][⛔] ➜ Hết đạo quân trống. Kết thúc![/bold red]")
            return
    else:
        console.print(f"[red][⚠️] ➜ Không tìm thấy mỏ {res_name}, chuyển sang lượt sau...[/red]")
        return gather_rss(device_id, sorted_res, count + 1, max_marches)

