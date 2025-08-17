import sys
import subprocess

REQUIRED_MODULES = [
    "rich",
    "pytesseract",
    "numpy",
    "opencv-python"
]

def install_missing_modules():
    for module in REQUIRED_MODULES:
        try:
            __import__(module.split("-")[0])
        except ImportError:
            print(f"[⚠️] ➜ Module '{module}' chưa có. Đang cài đặt...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", module])

install_missing_modules()

import os
import time
from rich.console import Console
from rich.table import Table
from rich import box

from adb_utils import list_devices, connect_devices, disconnect_devices
from game_utils import launch_game, close_game
from gather_rss import gather_rss
from clearfog import start_clear_fog  

console = Console()

def pause():
    console.input("\n[cyan][⚜️] ➜ Press [Enter] to return to menu...[/]")

def show_devices_once():
    devices = list_devices()
    table = Table(box=box.SQUARE, show_header=True, header_style="bold cyan", border_style="white")
    table.add_column("No.", justify="center", style="cyan", no_wrap=True)
    table.add_column("Device ID", justify="left", style="white")
    table.add_column("Status", justify="center", style="white", no_wrap=True)
    if not devices:
        table.add_row("-", "-", "🔴 Offline")
    else:
        for i, (device, status) in enumerate(devices, start=1):
            icon = "🟢 Online" if status == "online" else "🔴 Offline"
            table.add_row(str(i), device, icon)
    console.print(table)

def connect_flow():
    devices = list_devices()
    if not devices:
        console.print("[red][⚠️] ➜ No devices found![/red]")
        pause()
        return
    show_devices_once()
    sel = console.input("[cyan][⚜️] ➜ Enter device numbers (e.g. 1,2 or all): [/]").strip()
    results = connect_devices(sel, devices)
    for did, ok, msg in results:
        color = "green" if ok else "red"
        console.print(f"[{color}][✅] ➜ {did} ➜ {msg}[/{color}]")
    pause()

def disconnect_flow():
    devices = list_devices()
    if not devices:
        console.print("[red][⚠️] ➜ No devices found![/red]")
        pause()
        return
    show_devices_once()
    sel = console.input("[cyan][⚜️] ➜ Enter device numbers to disconnect (e.g. 1,2 or all): [/]").strip()
    results = disconnect_devices(sel, devices)
    for did, ok, msg in results:
        console.print(f"[yellow][⚜️] {did} ➜ {msg}[/yellow]")
    pause()

def launch_game_flow(package_name):
    devices = list_devices()
    if not devices:
        console.print("[red][⚠️] ➜ No devices found![/red]")
        pause()
        return
    show_devices_once()
    sel = console.input("[cyan][⚜️] ➜ Enter device numbers to launch game (e.g. 1,2 or all): [/]").strip()
    launch_game(sel, devices, package_name)
    pause()

def close_game_flow(package_name):
    devices = list_devices()
    if not devices:
        console.print("[red][⚠️] ➜ No devices found![/red]")
        pause()
        return
    show_devices_once()
    sel = console.input("[cyan][⚜️] ➜ Enter device numbers to close game (e.g. 1,2 or all): [/]").strip()
    close_game(sel, devices, package_name)
    pause()

def gather_rss_flow():
    devices = list_devices()
    if not devices:
        console.print("[red][⚠️] ➜ No devices found![/red]")
        pause()
        return

    show_devices_once()
    sel = console.input("[cyan][⚜️] ➜ Enter device numbers for Gather Rss (e.g. 1,2 or all): [/]").strip()

    if sel.lower() == "all":
        targets = [d[0] for d in devices if d[1] == "online"]
    else:
        targets = []
        for idx in sel.split(","):
            idx = idx.strip()
            if idx.isdigit() and 1 <= int(idx) <= len(devices):
                dev_id, status = devices[int(idx)-1]
                if status == "online":
                    targets.append(dev_id)
                else:
                    console.print(f"[yellow][⚠️] ➜ Skipping {dev_id} (offline)[/yellow]")

    for dev in targets:
        gather_rss(dev)

    pause()

def clear_fog_flow():
    devices = list_devices()
    if not devices:
        console.print("[red][⚠️] ➜ No devices found![/red]")
        pause()
        return

    show_devices_once()
    sel = console.input("[cyan][⚜️] ➜ Enter device number for Clear Fog (e.g. 1,2 or all): [/]").strip()

    if sel.isdigit() and 1 <= int(sel) <= len(devices):
        dev_id, status = devices[int(sel)-1]
        if status == "online":
            start_clear_fog(dev_id)   
        else:
            console.print(f"[yellow][⚠️] ➜ Skipping {dev_id} (offline)[/yellow]")
    else:
        console.print("[red][⚠️] ➜ Invalid selection[/red]")

    pause()

def main_menu():
    while True:
        os.system("cls" if os.name == "nt" else "clear")

        title_text = "🌸 Tool Rise Of Kingdoms 2025 🌸"
        line_len = len(title_text) + 6
        console.print("[bright_magenta]" + "╭" + "─" * (line_len-2) + "╮[/bright_magenta]")
        console.print(f"[bright_magenta]│[/bright_magenta] {title_text} [bright_magenta]│[/bright_magenta]")
        console.print("[bright_magenta]" + "╰" + "─" * (line_len-2) + "╯[/bright_magenta]")

        table = Table(show_header=False, box=None, expand=False, pad_edge=False)
        table.add_column("No.", justify="center", style="cyan", no_wrap=True)
        table.add_column("Option", justify="left", style="yellow")

        menu_items = [
            ("01", "[⚜️] Show Devices"),
            ("02", "[⚜️] Connect Device"),
            ("03", "[⚜️] Disconnect Device"),
            ("04", "[⚜️] Launch Game (GB)"),
            ("05", "[⚜️] Launch Game (VN)"),
            ("06", "[⚜️] Close Game (GB)"),
            ("07", "[⚜️] Close Game (VN)"),
            ("08", "[⚜️] Gather Rss"),
            ("09", "[⚜️] Clear Fog"),
            ("10","[⚜️] Exit\n")
        ]

        for no, text in menu_items:
            table.add_row(f"[cyan][{no}][/cyan]",text)

        console.print(table)

        choice = console.input("[yellow][⚜️] ➜ Choose an option: [/]").strip()

        if choice == "1":
            os.system("cls" if os.name == "nt" else "clear")
            show_devices_once()
            pause()
        elif choice == "2":
            os.system("cls" if os.name == "nt" else "clear")
            connect_flow()
        elif choice == "3":
            os.system("cls" if os.name == "nt" else "clear")
            disconnect_flow()
        elif choice == "4":
            os.system("cls" if os.name == "nt" else "clear")
            launch_game_flow("com.lilithgame.roc.gp")
        elif choice == "5":
            os.system("cls" if os.name == "nt" else "clear")
            launch_game_flow("com.rok.gp.vn")
        elif choice == "6":
            os.system("cls" if os.name == "nt" else "clear")
            close_game_flow("com.lilithgame.roc.gp")
        elif choice == "7":
            os.system("cls" if os.name == "nt" else "clear")
            close_game_flow("com.rok.gp.vn")
        elif choice == "8":
            os.system("cls" if os.name == "nt" else "clear")
            gather_rss_flow()
        elif choice == "9":
            os.system("cls" if os.name == "nt" else "clear")
            clear_fog_flow()
        elif choice == "10":
            console.print("[red]Exiting...[/red]")
            break
        else:
            console.print("[red][⛔] ➜ Invalid choice[/red]")
            time.sleep(0.8)

if __name__ == "__main__":
    main_menu()
