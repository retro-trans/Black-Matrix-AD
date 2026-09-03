"""Read Dreamcast RAM straight out of a running Dreamcast emulator process.

redream reserves the emulated SH-4 address space inside its own process and
logs where, e.g.

    sh4_space_init base=000001bd28bc0000

so SH-4 memory can be read live with ReadProcessMemory - no save state, no
emulator debugger.  The base is re-randomised every launch, so it is read back
out of redream.log each time.

    python tools/ramdump.py probe                 # find the process and base
    python tools/ramdump.py font                  # dump just the font sheet
    python tools/ramdump.py ram [out.bin]         # dump all 16 MB of main RAM

The game must be running and past the point where the font is installed - the
intro dialogue being on screen is a safe guarantee.
"""

import ctypes
import ctypes.wintypes as wt
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fontdump

REDREAM_LOG = r"M:\Program\Redream\redream.log"
RAM_BASE = 0x8C000000          # SH-4 P1, cached main RAM
RAM_SIZE = 16 * 1024 * 1024
PHYS_MASK = 0x1FFFFFFF         # SH-4 drops the top 3 bits to get physical

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
TH32CS_SNAPPROCESS = 0x00000002

k32 = ctypes.WinDLL("kernel32", use_last_error=True)


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wt.DWORD),
        ("__alignment1", wt.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wt.DWORD),
        ("Protect", wt.DWORD),
        ("Type", wt.DWORD),
        ("__alignment2", wt.DWORD),
    ]


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD),
        ("cntUsage", wt.DWORD),
        ("th32ProcessID", wt.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wt.DWORD),
        ("cntThreads", wt.DWORD),
        ("th32ParentProcessID", wt.DWORD),
        ("pcPriClassBase", wt.LONG),
        ("dwFlags", wt.DWORD),
        ("szExeFile", wt.WCHAR * 260),
    ]


# argtypes matter here: without them ctypes narrows the 64-bit handle to an
# int and every call fails silently.
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.OpenProcess.restype = wt.HANDLE
k32.VirtualQueryEx.argtypes = [wt.HANDLE, ctypes.c_void_p,
                               ctypes.POINTER(MEMORY_BASIC_INFORMATION),
                               ctypes.c_size_t]
k32.VirtualQueryEx.restype = ctypes.c_size_t
k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_size_t,
                                  ctypes.POINTER(ctypes.c_size_t)]
k32.ReadProcessMemory.restype = wt.BOOL
k32.CloseHandle.argtypes = [wt.HANDLE]
k32.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
k32.CreateToolhelp32Snapshot.restype = wt.HANDLE
k32.Process32FirstW.argtypes = [wt.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
k32.Process32FirstW.restype = wt.BOOL
k32.Process32NextW.argtypes = [wt.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
k32.Process32NextW.restype = wt.BOOL


def find_pid(name):
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap and snap != wt.HANDLE(-1).value:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        ok = k32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            if entry.szExeFile.lower() == name.lower():
                pid = entry.th32ProcessID
                k32.CloseHandle(snap)
                return pid
            ok = k32.Process32NextW(snap, ctypes.byref(entry))
        k32.CloseHandle(snap)

    # Compatibility fallback for older Windows environments.
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", "IMAGENAME eq " + name, "/FO", "CSV", "/NH"],
            stderr=subprocess.DEVNULL).decode("latin1")
    except Exception:
        return None
    m = re.search(r'"%s","(\d+)"' % re.escape(name), out)
    return int(m.group(1)) if m else None


def find_emulator():
    """Return (display name, pid, optional address-space base)."""
    pid = find_pid("redream.exe")
    if pid:
        return "redream", pid, log_base()
    pid = find_pid("flycast.exe")
    if pid:
        # Flycast does not expose redream's sh4_space_init log entry.  locate()
        # will scan its committed mappings for the game's installed font.
        return "flycast", pid, None
    return None


def log_base(path=REDREAM_LOG):
    """Last sh4_space_init base recorded in the log."""
    if not os.path.exists(path):
        return None
    found = None
    for line in open(path, "r", errors="replace"):
        m = re.search(r"sh4_space_init base=([0-9a-fA-F]+)", line)
        if m:
            found = int(m.group(1), 16)
    return found


class Proc(object):
    def __init__(self, pid):
        self.h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ,
                                 False, pid)
        if not self.h:
            raise OSError("OpenProcess failed (%d)" % ctypes.get_last_error())

    def read(self, addr, size):
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t(0)
        ok = k32.ReadProcessMemory(self.h, ctypes.c_void_p(addr), buf, size,
                                   ctypes.byref(got))
        return buf.raw[:got.value] if ok else None

    def regions(self, min_size=RAM_SIZE):
        mbi = MEMORY_BASIC_INFORMATION()
        addr = 0
        out = []
        while addr < 0x7FFFFFFFFFFF:
            n = k32.VirtualQueryEx(self.h, ctypes.c_void_p(addr),
                                   ctypes.byref(mbi), ctypes.sizeof(mbi))
            if not n:
                break
            if mbi.State == 0x1000 and mbi.RegionSize >= min_size:  # MEM_COMMIT
                out.append((mbi.BaseAddress or 0, mbi.RegionSize))
            addr = (mbi.BaseAddress or 0) + mbi.RegionSize
        return out


def candidates(base):
    """Plausible host addresses for SH-4 RAM, best guess first."""
    if base is None:
        return []
    return [
        ("base + physical", base + (RAM_BASE & PHYS_MASK)),
        ("base + virtual", base + RAM_BASE),
    ]


def locate(p, base):
    """Return (label, host address of SH-4 0x8C000000) or None."""
    for label, host in candidates(base):
        blob = p.read(host + fontdump.FONT_OFF, fontdump.FONT_LEN)
        if blob and fontdump.verify(blob, 0):
            return label, host
    # fall back to searching big committed regions for the sheet
    for rbase, rsize in p.regions():
        for off in range(0, min(rsize, 1 << 32) - RAM_SIZE + 1, RAM_SIZE):
            blob = p.read(rbase + off + fontdump.FONT_OFF, fontdump.FONT_LEN)
            if blob and fontdump.verify(blob, 0):
                return "scan", rbase + off
    return None


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "probe"
    emulator = find_emulator()
    if not emulator:
        print("Neither redream.exe nor flycast.exe is running.")
        print("Launch an emulator, load the disc, and get the target screen visible,")
        print("then run this again.")
        return 1
    name, pid, base = emulator
    print("%s pid %d, sh4_space base %s"
          % (name, pid, "%016X" % base if base else "scan required"))
    p = Proc(pid)

    hit = locate(p, base)
    if not hit:
        print("Could not find the font sheet in the process.")
        print("If the game has not drawn text yet, the sheet may not be")
        print("installed; advance to the intro dialogue and retry.")
        return 1
    label, host = hit
    print("SH-4 RAM at host %016X (%s)" % (host, label))
    print("font sheet at SH-4 %08X" % fontdump.FONT_ADDR)

    if cmd == "probe":
        return 0

    out_dir = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "extracted")
    os.makedirs(out_dir, exist_ok=True)

    if cmd == "font":
        blob = p.read(host + fontdump.FONT_OFF, fontdump.FONT_LEN)
        path = os.path.join(out_dir, "FONT.BIN")
        open(path, "wb").write(blob)
        print("wrote %s (%d bytes)" % (path, len(blob)))
        fontdump.verify(blob, 0, explain=True)
        for plane in (0, 1):
            png = os.path.join(out_dir, "font_plane%d.png" % plane)
            fontdump.sheet_png(blob, 0, png, first=0, count=512, plane=plane)
            print("wrote %s" % png)
        return 0

    if cmd == "ram":
        path = argv[2] if len(argv) > 2 else os.path.join(out_dir, "RAM.BIN")
        with open(path, "wb") as f:
            for off in range(0, RAM_SIZE, 1 << 20):
                chunk = p.read(host + off, 1 << 20)
                if chunk is None:
                    print("read failed at +%08X" % off)
                    return 1
                f.write(chunk)
        print("wrote %s (%d bytes, SH-4 %08X..)" % (path, RAM_SIZE, RAM_BASE))
        return 0

    print("unknown command:", cmd)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
