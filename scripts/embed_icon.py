"""Post-build icon embedding using ctypes with proper WINFUNCTYPE signatures."""
import struct
import sys
import ctypes
from ctypes import wintypes

kernel32 = ctypes.windll.kernel32

BeginUpdateResourceW = kernel32.BeginUpdateResourceW
BeginUpdateResourceW.argtypes = [wintypes.LPCWSTR, wintypes.BOOL]
BeginUpdateResourceW.restype = wintypes.HANDLE

UpdateResourceW = kernel32.UpdateResourceW
UpdateResourceW.argtypes = [
    wintypes.HANDLE, wintypes.LPCWSTR, wintypes.LPCWSTR,
    wintypes.WORD, ctypes.c_void_p, wintypes.DWORD,
]
UpdateResourceW.restype = wintypes.BOOL

EndUpdateResourceW = kernel32.EndUpdateResourceW
EndUpdateResourceW.argtypes = [wintypes.HANDLE, wintypes.BOOL]
EndUpdateResourceW.restype = wintypes.BOOL

RT_ICON = 3
RT_GROUP_ICON = 14

def MAKEINTRESOURCE(id_val: int):
    return ctypes.cast(ctypes.c_void_p(id_val & 0xFFFF), wintypes.LPCWSTR)

def embed_icon(exe_path: str, ico_path: str):
    with open(ico_path, "rb") as f:
        raw = f.read()

    count = struct.unpack_from("<H", raw, 4)[0]
    pos = 6
    icon_resources = []
    entries = []

    for i in range(count):
        w, h, colors, reserved, planes, bpp, size, offset = struct.unpack_from(
            "<BBBBHHII", raw, pos
        )
        data = raw[offset:offset + size]
        icon_id = i + 1
        entries.append((w, h, colors, planes, bpp, size, icon_id))
        icon_resources.append((icon_id, data))
        pos += 16

    group_data = struct.pack("<HHH", 0, 1, count)
    for w, h, colors, planes, bpp, size, icon_id in entries:
        group_data += struct.pack(
            "<BBBBHHII", w, h, colors, 0, planes, bpp, size, icon_id
        )

    handle = BeginUpdateResourceW(exe_path, False)
    if not handle:
        error = ctypes.GetLastError()
        print(f"ERROR: BeginUpdateResourceW failed (error {error})")
        return False

    try:
        for icon_id, data in icon_resources:
            ret = UpdateResourceW(
                handle,
                MAKEINTRESOURCE(RT_ICON),
                MAKEINTRESOURCE(icon_id),
                0x0409, data, len(data),
            )
            if not ret:
                error = ctypes.GetLastError()
                print(f"ERROR: UpdateResourceW RT_ICON {icon_id} (error {error})")
                return False
            print(f"  RT_ICON {icon_id}: {len(data)}B OK")

        ret = UpdateResourceW(
            handle,
            MAKEINTRESOURCE(RT_GROUP_ICON),
            MAKEINTRESOURCE(1),
            0x0409, group_data, len(group_data),
        )
        if not ret:
            error = ctypes.GetLastError()
            print(f"ERROR: UpdateResourceW RT_GROUP_ICON (error {error})")
            return False
        print(f"  RT_GROUP_ICON: {len(group_data)}B OK")

        if not EndUpdateResourceW(handle, False):
            error = ctypes.GetLastError()
            print(f"ERROR: EndUpdateResourceW (error {error})")
            return False

        print("Icon embedded successfully!")
        return True
    except Exception as e:
        EndUpdateResourceW(handle, True)
        print(f"ERROR: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: embed_icon.py <exe_path> <ico_path>")
        sys.exit(1)
    sys.exit(0 if embed_icon(sys.argv[1], sys.argv[2]) else 1)
