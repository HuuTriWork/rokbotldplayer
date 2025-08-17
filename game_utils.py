import subprocess
from rich.console import Console

from adb_utils import ADB_PATH

console = Console()

def launch_game(selection, devices, package_name):
    online_devices = [d for d in devices if d[1] == "online"]
    if not online_devices:
        console.print("[red]No online devices available to launch game[/red]")
        return

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
                else:
                    console.print(f"[yellow]⚠ Skipping {dev_id} (offline)[/yellow]")

    for dev in targets:
        subprocess.run([ADB_PATH, "-s", dev, "shell", "monkey",
                        "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        console.print(f"[green]📂 Launched {package_name} on {dev}[/green]")

def close_game(selection, devices, package_name):
    online_devices = [d for d in devices if d[1] == "online"]
    if not online_devices:
        console.print("[red]No online devices available to close game[/red]")
        return

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
                else:
                    console.print(f"[yellow]⚠ Skipping {dev_id} (offline)[/yellow]")

    for dev in targets:
        subprocess.run([ADB_PATH, "-s", dev, "shell", "am", "force-stop", package_name],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        console.print(f"[red]🛑 Closed {package_name} on {dev}[/red]")
