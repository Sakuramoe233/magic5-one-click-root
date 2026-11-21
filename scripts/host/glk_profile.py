#!/usr/bin/env python3
"""GhostLock profile.bin (wire v2) <-> text tooling.

Wire layout (src/core/profile/binary.cpp):
  header  : u32 magic 0x0D000721, u16 version=2, u16 frontend, u16 backend,
            u16 middleware/route, u16 release_len
  release : release_len bytes (uname -r), no terminator
  u16 section_count
  section : u8 name_len, name, u32 entry_count
  entry   : u8 key_len, key, u64 value (little endian)
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

MAGIC = 0x0D000721
VERSION = 2

ROUTES = {"tcp_zerocopy": 1, "select_stack": 2, "multicast_waiter": 3}
ROUTE_NAMES = {v: k for k, v in ROUTES.items()}

SECTION_ORDER = [
    "meta",
    "task_struct",
    "cred",
    "offset",
    "kernel",
    "execution.recommended_cpus",
    "execution.heap",
    "execution.race",
    "execution.stages",
    "execution.handoff",
    "execution.consumer",
    "route.tcp_zerocopy",
    "route.select_stack",
    "route.multicast_waiter",
]

# conf key -> (section, wire key). Conf keys are flat: task_struct.cred,
# offset.init_cred, route.multicast_waiter.waiter_off, ...
CONF_ALIASES = {
    "kernelsnitch.collisions": ("kernel", "kernelsnitch_collisions"),
    "kernelsnitch.mm_struct_sz": ("kernel", "mm_struct_sz"),
    "route.multicast_waiter.waiter_off": ("route.multicast_waiter", "waiter_off"),
    "route.multicast_waiter.buffer_size": ("route.multicast_waiter", "buffer_size"),
    "route.multicast_waiter.task_offset": ("route.multicast_waiter", "task_offset"),
    "route.multicast_waiter.lock_offset": ("route.multicast_waiter", "lock_offset"),
    "route.multicast_waiter.compact_waiter": ("kernel", "compact_waiter"),
    "route.select_stack.waiter_shift": ("route.select_stack", "waiter_shift"),
}


def parse_bin(data: bytes) -> dict:
    if len(data) < 16:
        raise ValueError("short profile")
    magic, version, frontend, backend, route, release_len = struct.unpack_from(
        "<IHHHHH", data, 0
    )
    if magic != MAGIC or version != VERSION:
        raise ValueError(f"bad header magic={magic:#x} version={version}")
    release = data[16 : 16 + release_len].decode("utf-8", "replace")
    pos = 16 + release_len
    (section_count,) = struct.unpack_from("<H", data, pos)
    pos += 2
    sections: dict[str, dict[str, int]] = {}
    for _ in range(section_count):
        name_len = data[pos]
        pos += 1
        name = data[pos : pos + name_len].decode()
        pos += name_len
        (entries,) = struct.unpack_from("<I", data, pos)
        pos += 4
        fields: dict[str, int] = {}
        for _ in range(entries):
            key_len = data[pos]
            pos += 1
            key = data[pos : pos + key_len].decode()
            pos += key_len
            (value,) = struct.unpack_from("<Q", data, pos)
            pos += 8
            fields[key] = value
        sections[name] = fields
    return {
        "frontend": frontend,
        "backend": backend,
        "route": route,
        "release": release,
        "sections": sections,
        "trailing": len(data) - pos,
    }


def serialize(profile: dict) -> bytes:
    release = profile["release"].encode()
    out = bytearray()
    out += struct.pack(
        "<IHHHHH",
        MAGIC,
        VERSION,
        profile["frontend"],
        profile["backend"],
        profile["route"],
        len(release),
    )
    # kHeaderSize is 16: the six wire fields occupy 14 bytes, then 2 reserved.
    out += b"\x00\x00"
    out += release
    names = [n for n in SECTION_ORDER if profile["sections"].get(n)]
    for extra in sorted(profile["sections"]):
        if extra not in SECTION_ORDER and profile["sections"][extra]:
            names.append(extra)
    out += struct.pack("<H", len(names))
    for name in names:
        fields = profile["sections"][name]
        encoded_name = name.encode()
        out += bytes([len(encoded_name)]) + encoded_name
        out += struct.pack("<I", len(fields))
        for key, value in fields.items():
            encoded_key = key.encode()
            out += bytes([len(encoded_key)]) + encoded_key
            out += struct.pack("<Q", value & 0xFFFFFFFFFFFFFFFF)
    return bytes(out)


def signed(value: int) -> int:
    return value - (1 << 64) if value >> 63 else value


def parse_conf(path: Path) -> dict[str, int | str]:
    """Flatten the extractor's HOCON output into dotted keys."""
    flat: dict[str, int | str] = {}
    stack: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.endswith("{"):
            stack.append(line[:-1].strip())
            continue
        if line.startswith("}"):
            if stack:
                stack.pop()
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().rstrip(",")
        dotted = ".".join(stack + [key])
        if value.startswith('"'):
            flat[dotted] = value.strip('"')
        elif value in ("null", "true", "false"):
            flat[dotted] = value
        else:
            try:
                flat[dotted] = int(value, 0)
            except ValueError:
                flat[dotted] = value
    return flat


def apply_conf(profile: dict, conf: dict[str, int | str]) -> list[str]:
    """Overwrite wire fields from the flattened conf. Returns changed keys."""
    changed = []
    for key, value in conf.items():
        if isinstance(value, str):
            if key == "release":
                profile["release"] = value
            continue
        if key in CONF_ALIASES:
            section, wire_key = CONF_ALIASES[key]
        elif "." in key:
            section, wire_key = key.rsplit(".", 1)
        else:
            continue
        if section == "meta":
            wire_key = {"kernel_major": "kernel_major"}.get(wire_key, wire_key)
        profile["sections"].setdefault(section, {})[wire_key] = value & 0xFFFFFFFFFFFFFFFF
        changed.append(f"{section}.{wire_key}")
    return changed


def dump(profile: dict) -> str:
    lines = [
        f"release     : {profile['release']}",
        f"frontend    : {profile['frontend']}",
        f"backend     : {profile['backend']}",
        f"route       : {profile['route']} ({ROUTE_NAMES.get(profile['route'], '?')})",
        f"trailing    : {profile['trailing']} bytes",
    ]
    for name in SECTION_ORDER + [n for n in profile["sections"] if n not in SECTION_ORDER]:
        fields = profile["sections"].get(name)
        if not fields:
            continue
        lines.append(f"[{name}]")
        for key, value in fields.items():
            lines.append(f"  {key:<28} {signed(value):>18}   0x{value:x}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_dump = sub.add_parser("dump", help="print a profile.bin")
    p_dump.add_argument("bin")

    p_pack = sub.add_parser("pack", help="overlay a .conf onto a template .bin")
    p_pack.add_argument("--template", required=True)
    p_pack.add_argument("--conf", required=True)
    p_pack.add_argument("--out", required=True)
    p_pack.add_argument("--route", default=None, choices=sorted(ROUTES))
    p_pack.add_argument("--release", default=None)

    p_round = sub.add_parser("roundtrip", help="parse+serialize and compare bytes")
    p_round.add_argument("bin")

    args = ap.parse_args()

    if args.cmd == "dump":
        print(dump(parse_bin(Path(args.bin).read_bytes())))
        return 0

    if args.cmd == "roundtrip":
        original = Path(args.bin).read_bytes()
        rebuilt = serialize(parse_bin(original))
        print(f"original={len(original)} rebuilt={len(rebuilt)} identical={original == rebuilt}")
        return 0 if original == rebuilt else 1

    profile = parse_bin(Path(args.template).read_bytes())
    conf = parse_conf(Path(args.conf))
    if args.route:
        profile["route"] = ROUTES[args.route]
    if args.release:
        profile["release"] = args.release
    changed = apply_conf(profile, conf)
    blob = serialize(profile)
    Path(args.out).write_bytes(blob)
    print(f"wrote {args.out} ({len(blob)} bytes), {len(changed)} fields overlaid")
    print(dump(profile))
    return 0


if __name__ == "__main__":
    sys.exit(main())
