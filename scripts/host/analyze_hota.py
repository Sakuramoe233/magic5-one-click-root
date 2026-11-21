#!/usr/bin/env python3
"""分析 HOTA / OUC logcat 抓包，提取完整包下载线索。

用法:
    python analyze_hota.py hota_capture.log [snapshot.log ...]

输出:
    - 终端: URL 分类摘要、疑似固件包 URL(带上下文)、HOTA/OUC 关键日志行、版本号线索
    - 文件: hota_urls.txt (去重后的全部 URL)
"""
import re
import sys
from collections import OrderedDict

URL_RE = re.compile(r"https?://[^\s\"'<>\\，。；、（）【】\)\]\}]+")
# 疑似固件 / 更新包的特征
PKG_RE = re.compile(
    r"\.(zip|bin|app|img|gz|tar|md5)(\?|$)|\.(zip|bin|app|img)\b"
    r"|/(pkg|package|packages|full|fullpkg|dload|firmware|ota|update|download)s?/"
    r"|hota|dbankcdn|hicloud|hihonor.*update|update.*hihonor|query\.hihonor|hwouc|ouc",
    re.I,
)
OTA_TAG_RE = re.compile(
    r"hota|ouc|ota|update|dload|download|firmware|payload|hnouc|OtaService|UpdateEngine|DownloadManager|HwOUC|SystemUpdate",
    re.I,
)
VER_RE = re.compile(r"\b\d+\.\d+\.\d+\.\d+\b|\b5\.15\.\d+(?:-android\d+-\d+-g[0-9a-f]+)?\b|\bPGT-[A-Z0-9]+\b")


def main() -> int:
    paths = sys.argv[1:]
    if not paths:
        print(__doc__)
        return 1

    lines = []
    for p in paths:
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                chunk = f.read().splitlines()
            print(f"[+] {p}: {len(chunk)} 行")
            lines.extend((p, i + 1, ln) for i, ln in enumerate(chunk))
        except OSError as e:
            print(f"[!] 无法读取 {p}: {e}")

    if not lines:
        print("[!] 日志为空，稍等几秒再试")
        return 2

    all_urls = OrderedDict()
    pkg_urls = []
    ota_lines = []
    ver_lines = []

    for src, lineno, line in lines:
        for raw in URL_RE.findall(line):
            u = raw.rstrip(".,;:")
            if u not in all_urls:
                all_urls[u] = (src, lineno, line.strip())
        if PKG_RE.search(line) and URL_RE.search(line):
            pkg_urls.append((src, lineno, line.strip()))
        if OTA_TAG_RE.search(line):
            ota_lines.append((src, lineno, line.strip()))
        if VER_RE.search(line) and OTA_TAG_RE.search(line):
            ver_lines.append((src, lineno, line.strip()))

    print(f"\n=== 汇总: {len(lines)} 行日志, {len(all_urls)} 个去重 URL, "
          f"{len(pkg_urls)} 行疑似固件/更新 URL ===")

    print("\n=== 疑似固件包 / 更新服务器 URL (带上下文) ===")
    if not pkg_urls:
        print("(暂无)")
    seen_ctx = set()
    for src, lineno, line in pkg_urls[:40]:
        key = line[:160]
        if key in seen_ctx:
            continue
        seen_ctx.add(key)
        print(f"\n--- {src}:{lineno}")
        # 打印相邻 2 行上下文
        idx = next((i for i, (s, n, _) in enumerate(lines)
                    if s == src and n == lineno), None)
        if idx is not None:
            for s, n, ctx in lines[max(0, idx - 2):idx + 3]:
                print(f"  {n}: {ctx[:400]}")
        else:
            print(f"  {line[:400]}")

    print("\n=== 全部 URL (按命中优先级) ===")
    for u, (src, lineno, line) in all_urls.items():
        mark = " *" if PKG_RE.search(u) else "  "
        print(f"{mark} {u[:300]}")
        if PKG_RE.search(u):
            print(f"      <- {src}:{lineno}: {line[:200]}")

    print(f"\n=== HOTA/OUC 关键日志行 (最多 120 条) ===")
    for src, lineno, line in ota_lines[-120:]:
        print(f"  {lineno}: {line[:300]}")

    print(f"\n=== 版本号线索 (最多 60 条) ===")
    for src, lineno, line in ver_lines[-60:]:
        print(f"  {lineno}: {line[:300]}")

    out = "hota_urls.txt"
    with open(out, "w", encoding="utf-8") as f:
        for u in all_urls:
            f.write(u + "\n")
    print(f"\n[+] 全部 URL 已写入 {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
