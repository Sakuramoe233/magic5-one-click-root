# profiles/

| 文件 | 说明 |
|---|---|
| `profile_175.conf` | GhostLock kernel profile（HOCON，自包含），对应内核 `5.15.180-android13-8-g1c54d617912d`。字段来自设备 `boot.img` / OTA 的偏移提取，包含 `task_struct` 各成员偏移、`route.multicast_waiter`、`kernelsnitch` 等配置 |
| `profile_175.bin` | 由该 conf 导出的二进制 profile，**不在本仓库中**（`.gitignore` 排除 `*.bin`）。生成时把 `prepare_max_attempts` 从上游默认的 4 调整为 60 以提高成功率；成品中随包提供 |

该 profile 属于 [GhostLock](https://github.com/YuKongA/ghostlock-app) 项目定义的格式与派生数据，许可证为 Apache-2.0。它**硬绑定这一颗内核**，换内核即失效。

生成与使用方式见 [docs/BUILD.md](../docs/BUILD.md) 第 5 步，以及 `kit/payload/kit-root.sh` 中的 `--load-prebuilt-profile` 调用。
