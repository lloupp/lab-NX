"""Vulkan ICD capability probe and isolated, SHA-256-checked Mesa Lavapipe staging.

Never reads commercial games, runs with no root privileges, and never
modifies the system Vulkan loader configuration.
"""
from __future__ import annotations
import argparse
import ctypes as c
import ctypes.util
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

TRIXIE_MESA_SHA256 = "caf2f7d296b7522efe74e40a74bce762a3ce84c33b53b5e54e1248ac2e0a13a5"


class VulkanError(ValueError):
    pass


class VkApplicationInfo(c.Structure):
    _fields_ = [
        ("sType", c.c_uint32), ("pNext", c.c_void_p),
        ("pApplicationName", c.c_char_p), ("applicationVersion", c.c_uint32),
        ("pEngineName", c.c_char_p), ("engineVersion", c.c_uint32),
        ("apiVersion", c.c_uint32)
    ]


class VkInstanceCreateInfo(c.Structure):
    _fields_ = [
        ("sType", c.c_uint32), ("pNext", c.c_void_p),
        ("flags", c.c_uint32), ("pApplicationInfo", c.POINTER(VkApplicationInfo)),
        ("enabledLayerCount", c.c_uint32), ("ppEnabledLayerNames", c.c_void_p),
        ("enabledExtensionCount", c.c_uint32), ("ppEnabledExtensionNames", c.c_void_p)
    ]


def api_version(value):
    return ((value >> 22) & 127, (value >> 12) & 1023, value & 4095)


def probe(icd=None):
    previous = {k: os.environ.get(k) for k in ("VK_DRIVER_FILES", "VK_ICD_FILENAMES")}
    if icd is not None:
        path = Path(icd).expanduser().resolve(strict=True)
        config = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(config, dict) or not isinstance(config.get("ICD"), dict):
            raise VulkanError("Invalid Vulkan ICD manifest")
        os.environ["VK_DRIVER_FILES"] = str(path)
        os.environ["VK_ICD_FILENAMES"] = str(path)
    try:
        name = ctypes.util.find_library("vulkan")
        if not name:
            return {"loader_available": False, "device_count": 0,
                    "geometry_shader_device_available": False,
                    "reason": "No Vulkan loader"}
        vk = c.CDLL(name)
        get_version = getattr(vk, "vkEnumerateInstanceVersion", None)
        version = c.c_uint32(1 << 22)
        if get_version is not None:
            get_version.argtypes = [c.POINTER(c.c_uint32)]
            get_version.restype = c.c_int32
            if get_version(c.byref(version)):
                raise VulkanError("Failed to read Vulkan loader version")
        requested = min(version.value, (1 << 22) | (1 << 12))
        app = VkApplicationInfo(0, None, b"lab-NX", 1, b"lab-NX", 1, requested)
        config = VkInstanceCreateInfo(1, None, 0, c.pointer(app), 0, None, 0, None)
        vk.vkCreateInstance.argtypes = [c.POINTER(VkInstanceCreateInfo),
                                        c.c_void_p, c.POINTER(c.c_void_p)]
        vk.vkCreateInstance.restype = c.c_int32
        instance = c.c_void_p()
        rc = vk.vkCreateInstance(c.byref(config), None, c.byref(instance))
        result = {"loader_available": True, "loader_version": api_version(version.value),
                  "vk_create_instance_code": rc, "devices": [], "device_count": 0,
                  "vulkan11_device_available": False,
                  "geometry_shader_device_available": False}
        if rc:
            result["reason"] = "No compatible Vulkan ICD detected"
            return result
        try:
            vk.vkEnumeratePhysicalDevices.argtypes = [c.c_void_p,
                                                      c.POINTER(c.c_uint32), c.c_void_p]
            vk.vkEnumeratePhysicalDevices.restype = c.c_int32
            total = c.c_uint32()
            if vk.vkEnumeratePhysicalDevices(instance, c.byref(total), None) or total.value > 32:
                raise VulkanError("Physical device enumeration failed")
            result["device_count"] = total.value
            if not total.value:
                return result
            devices = (c.c_void_p * total.value)()
            if vk.vkEnumeratePhysicalDevices(instance, c.byref(total), devices):
                raise VulkanError("Physical device handles unavailable")
            vk.vkGetPhysicalDeviceProperties.argtypes = [c.c_void_p, c.c_void_p]
            vk.vkGetPhysicalDeviceFeatures.argtypes = [c.c_void_p, c.c_void_p]
            for device in devices:
                properties = c.create_string_buffer(4096)
                features = c.create_string_buffer(512)
                vk.vkGetPhysicalDeviceProperties(device, c.byref(properties))
                vk.vkGetPhysicalDeviceFeatures(device, c.byref(features))
                driver_version = int.from_bytes(properties.raw[:4], "little")
                geometry = bool(int.from_bytes(features.raw[16:20], "little"))
                name = properties.raw[20:276].split(b"\0", 1)[0].decode("utf-8", "replace")
                item = {"name": name, "api_version": api_version(driver_version),
                        "geometry_shader": geometry}
                result["devices"].append(item)
                if item["api_version"][:2] >= (1, 1):
                    result["vulkan11_device_available"] = True
                    if geometry:
                        result["geometry_shader_device_available"] = True
            return result
        finally:
            vk.vkDestroyInstance.argtypes = [c.c_void_p, c.c_void_p]
            vk.vkDestroyInstance(instance, None)
    finally:
        for key, original in previous.items():
            if original is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original


def stage_deb(deb, out):
    """Install only the pinned Debian 13 Mesa package into new private directory."""
    package = Path(deb).expanduser().resolve(strict=True)
    folder = Path(out).expanduser().resolve()
    if package.stat().st_size > 60 * 1024 * 1024:
        raise VulkanError("Debian package too large")
    digest = hashlib.sha256()
    with package.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            digest.update(chunk)
    if digest.hexdigest() != TRIXIE_MESA_SHA256:
        raise VulkanError("Unverified Debian package SHA-256")
    if folder.exists() or any((parent / ".git").exists() for parent in (folder, *folder.parents)):
        raise VulkanError("Use a NEW directory outside Git")
    folder.mkdir(parents=True, mode=0o700)
    try:
        action = subprocess.run(["dpkg-deb", "-x", str(package), str(folder)],
                                capture_output=True, text=True, timeout=90, check=False)
        if action.returncode:
            raise VulkanError("dpkg-deb extraction failed")
        binary = folder / "usr/lib/x86_64-linux-gnu/libvulkan_lvp.so"
        source_icd = folder / "usr/share/vulkan/icd.d/lvp_icd.json"
        if not binary.is_file() or not source_icd.is_file():
            raise VulkanError("Verified package lacks Lavapipe ICD")
        manifest = json.loads(source_icd.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or not isinstance(manifest.get("ICD"), dict):
            raise VulkanError("Invalid system ICD manifest")
        manifest["ICD"]["library_path"] = str(binary)
        target = folder / "labnx-lavapipe-icd.json"
        target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return target
    except BaseException:
        shutil.rmtree(folder, ignore_errors=True)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description="Vulkan Xenos preflight (no game files)")
    actions = parser.add_subparsers(dest="action", required=True)
    p = actions.add_parser("probe")
    p.add_argument("--icd", type=Path)
    p = actions.add_parser("stage")
    p.add_argument("--deb", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == "stage":
            icd = stage_deb(args.deb, args.out)
            print(json.dumps({"private_icd": str(icd)}))
            return 0
        result = probe(args.icd)
        print(json.dumps(result, indent=2))
        return 0 if result.get("vulkan11_device_available") else 3
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"lab-NX Vulkan doctor: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
