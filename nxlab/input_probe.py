"""Read-only SDL controller availability probe for Castle Crashers title screen.

Does not inject input, claim a successful Start press, or access game files.
"""
import argparse
import ctypes
import ctypes.util
import json


def probe_sdl():
    name = ctypes.util.find_library("SDL3")
    if not name:
        return {"sdl3_found": False, "gamepads": [], "connected": 0}
    sdl = ctypes.CDLL(name)
    sdl.SDL_Init.argtypes = [ctypes.c_uint32]
    sdl.SDL_Init.restype = ctypes.c_bool
    sdl.SDL_GetGamepads.argtypes = [ctypes.POINTER(ctypes.c_int)]
    sdl.SDL_GetGamepads.restype = ctypes.POINTER(ctypes.c_uint32)
    sdl.SDL_GetGamepadNameForID.argtypes = [ctypes.c_uint32]
    sdl.SDL_GetGamepadNameForID.restype = ctypes.c_char_p
    sdl.SDL_free.argtypes = [ctypes.c_void_p]
    sdl.SDL_Quit.argtypes = []
    # SDL_INIT_GAMEPAD=0x00002000; SDL_INIT_JOYSTICK=0x00000200.
    if not sdl.SDL_Init(0x00002200):
        return {"sdl3_found": True, "init_ok": False, "connected": 0, "gamepads": []}
    try:
        count = ctypes.c_int(0)
        ids = sdl.SDL_GetGamepads(ctypes.byref(count))
        names = []
        if ids:
            try:
                for i in range(min(count.value, 16)):
                    raw = sdl.SDL_GetGamepadNameForID(ids[i])
                    names.append({"id": int(ids[i]), "name": raw.decode("utf-8", "replace") if raw else "unknown"})
            finally:
                sdl.SDL_free(ids)
        return {"sdl3_found": True, "init_ok": True,
                "connected": len(names), "gamepads": names,
                "start_button_verified": False}
    finally:
        sdl.SDL_Quit()


def main():
    parser = argparse.ArgumentParser()
    parser.parse_args()
    print(json.dumps(probe_sdl(), indent=2))


if __name__ == "__main__":
    main()
