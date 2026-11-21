# 使用说明（精简版）

> 完整的中文说明（含常见问题、目录结构、SELinux / su / 管理器版本的解释）见工具包内的 **[kit/使用说明.txt](../kit/使用说明.txt)**，该文件随 Release ZIP 一起分发。

## 适用条件

- 机型：HONOR Magic5 `PGT-AN00`
- 内核：`5.15.180-android13-8-g1c54d617912d`
- 系统：与该内核对应的同一版 MagicOS（10.0.0.175）
- 电脑：Windows 10/11（PowerShell 5.1 自带），USB 数据线

`kit/tools/kit.ps1` 启动时会核对机型与 `uname -r`，不匹配立即停止。不要对其它机型或 OTA 后的系统使用 `-Force`。

## 步骤

1. 从 Releases 下载 `Magic5一键提权-USB调试版.zip`，解压到任意目录（路径含空格也可以）。
2. 手机开启「开发者选项 → USB 调试」；连接数据线、解锁屏幕，勾选「一律允许 USB 调试」。
3. 若设备管理器里没有 ADB 接口，先安装 `usb_driver`（手动更新驱动指向该目录），然后重插数据线。
4. 双击 `一键提权.bat`，等待 1–2 分钟，窗口会打印每一步的结果。
5. 打开手机上的 ReSukiSU / BakaSU，应显示「工作中 · LKM · 越狱模式」，版本 `35257 / 6`。

工具包自带 `adb.exe` 与全部载荷，电脑上**不需要** Python、Java、Android SDK 或独立安装的 adb。

## 三个入口

| 入口 | 行为 |
|---|---|
| `一键提权.bat` | 完整流程（临时 root → 关验签 → 导 kallsyms → 补丁 → insmod） |
| `仅临时root.bat` | 只取 adb shell 的 root，不加载 KSU 模块 |
| `查看状态.bat` | 只读状态检查，不改动设备 |

命令行等价用法：

```powershell
powershell -ExecutionPolicy Bypass -File tools\kit.ps1 -Status
powershell -ExecutionPolicy Bypass -File tools\kit.ps1 -RootOnly
powershell -ExecutionPolicy Bypass -File tools\kit.ps1 -Shell
powershell -ExecutionPolicy Bypass -File tools\kit.ps1 -Module x.ko
```

## 需要知道的行为

- **临时 root**：全部改动只在内存与 `/data/local/tmp`，不写 boot 分区。手机重启后失效，需重新运行。
- **SELinux 保持 Permissive**：Honor 的 HKIP 定制 SELinux 策略与 AOSP `policydb` 布局不兼容，KSU 重载策略会把网络包标成 `unlabeled`，导致 WiFi / 数据「有信号、有 IP、全都不通」。保持 permissive 是功能取舍。重启且不运行本工具时系统回到 Enforcing。
- **`/system/bin/su` 不存在是正常的**：KSU 用 `sucompat` 的 execve 钩子按管理器的授权列表决定是否放行；给某个 App root 需在管理器「超级用户」页授权。
- 要用 adb 侧的临时 root：`adb shell /data/local/tmp/su -c "id"`。

## 常见问题

| 现象 | 处理 |
|---|---|
| 没找到设备 | 解锁屏幕、重插数据线、装 `usb_driver`、通知栏 USB 用途改为「传输文件」；荣耀电脑管家可能占用 5037，脚本会尝试结束 `hwtransport.exe` 并重启 adb server |
| 设备未授权 | 手机上点「允许」并勾「一律允许」，再跑一次 |
| 提权步骤失败 | 漏洞本身有概率性，直接重跑；连续两次失败就重启手机 |
| `insmod` 返回非 0 | 多半是 `sig_enforce` 没清干净，重启手机重跑 |
| 跑完 USB 掉线 | 保持屏幕解锁、重插数据线；模块通常仍在运行，用 `查看状态.bat` 确认，不必重复提权 |

排错请看工具包目录下自动生成的 `kit-<时间>.log`，其中记录每条 adb 命令与返回码。

## 安全提示

仅用于你本人拥有的设备。加载内核模块、关闭 SELinux 强制存在系统不稳定与数据风险，请先备份重要资料。详见根目录 README 的免责声明。
