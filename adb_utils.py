import subprocess

ADB_PATH = "adb\\adb.exe"
connected_devices = set()

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
