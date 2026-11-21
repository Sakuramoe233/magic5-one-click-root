<#
    Magic5 (PGT-AN00) 一键提权  ——  PC / USB 版
    ---------------------------------------------------------------
    流程：临时 root -> 关模块验签 -> 导本次开机 kallsyms -> 按 KASLR 重写
          模块符号 -> insmod -> 交给 BakaSU / ReSukiSU 管理器接管。

    用法（一般直接双击 exe/bat，不用手敲）：
        powershell -ExecutionPolicy Bypass -File kit.ps1
        powershell ... -File kit.ps1 -RootOnly        只取临时 root
        powershell ... -File kit.ps1 -Shell           取到 root 后进 root shell
        powershell ... -File kit.ps1 -Status          只看状态，不动设备
        powershell ... -File kit.ps1 -Force           内核版本不匹配也继续（危险）

    说明：模块的代码段偏移、结构体布局都是针对
          5.15.180-android13-8-g1c54d617912d 这一个内核编译的，
          换内核（哪怕是同型号的系统更新）都必须重新编译，否则必 panic。
#>
[CmdletBinding()]
param(
    [switch]$RootOnly,
    [switch]$Shell,
    [switch]$Status,
    [switch]$Force,
    [string]$Module = ''
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# cmd 窗口标题：bat 里已设一份，这里用 Unicode 再设一次，
# 避免非中文系统下 bat 中的中文标题乱码。
try {
    $kitMode = if ($Status) { '状态查看' } elseif ($RootOnly) { '临时 Root' } else { '一键提权' }
    [Console]::Title = "Magic5 $kitMode by：夜空的花火i"
} catch { }

# ------------------------------------------------------------------ 常量
$script:KitRoot = Split-Path -Parent $PSScriptRoot
$script:Payload = Join-Path $script:KitRoot 'payload'
$script:Adb = Join-Path $PSScriptRoot 'adb.exe'
$script:Work = Join-Path $env:TEMP ('magic5kit-' + $PID)
$script:LogFile = Join-Path $script:KitRoot ('kit-' + (Get-Date -Format 'MMdd-HHmmss') + '.log')
$script:Serial = $null
$script:StepNo = 0
$script:StepAll = 7

$KERNEL_WANT = '5.15.180-android13-8-g1c54d617912d'
$MODEL_WANT = 'PGT-AN00'
$ZERO_ADDR = '0xffffffc0830c7708'   # sig_enforce 的名义地址
$MOD_NAME = 'ksu-magic5-35257-uapi6.ko'
$DEV_MOD = '/data/local/tmp/ksu-kit.ko'

# ------------------------------------------------------------------ 输出
function Write-Log([string]$m) {
    try { [System.IO.File]::AppendAllText($script:LogFile, $m + "`r`n", [System.Text.UTF8Encoding]::new($false)) } catch { }
}
function Say([string]$m) { Write-Host $m }
function Step([string]$m) {
    $script:StepNo++
    Write-Host ''
    Write-Host ("[{0}/{1}] {2}" -f $script:StepNo, $script:StepAll, $m) -ForegroundColor Cyan
    Write-Log ("== {0}" -f $m)
}
function Ok([string]$m) { Write-Host ("       [+] " + $m) -ForegroundColor Green; Write-Log ("  ok   " + $m) }
function Info([string]$m) { Write-Host ("       -   " + $m) -ForegroundColor DarkGray; Write-Log ("  ..   " + $m) }
function Warn([string]$m) { Write-Host ("       [!] " + $m) -ForegroundColor Yellow; Write-Log ("  warn " + $m) }
function Bad([string]$m) { Write-Host ("       [x] " + $m) -ForegroundColor Red; Write-Log ("  err  " + $m) }

function Die([string]$m) {
    Write-Host ''
    Write-Host ('  [失败] ' + $m) -ForegroundColor Red
    Write-Log ('FATAL ' + $m)
    Write-Host ''
    Write-Host ('  详细日志：' + $script:LogFile) -ForegroundColor DarkGray
    Write-Host ''
    exit 1
}

# ------------------------------------------------------------------ 执行器
function Quote-Arg([string]$s) {
    if ($null -eq $s -or $s -eq '') { return '""' }
    if ($s -notmatch '[\s"]') { return $s }
    return '"' + ($s -replace '"', '\"') + '"'
}

function Invoke-Exe {
    param([string]$File, [string[]]$Argv, [int]$TimeoutSec = 120)
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $File
    $psi.Arguments = (($Argv | ForEach-Object { Quote-Arg $_ }) -join ' ')
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8

    $p = New-Object System.Diagnostics.Process
    $p.StartInfo = $psi
    [void]$p.Start()
    $o = $p.StandardOutput.ReadToEndAsync()
    $e = $p.StandardError.ReadToEndAsync()
    $done = $p.WaitForExit($TimeoutSec * 1000)
    if (-not $done) {
        try { $p.Kill() } catch { }
        return [pscustomobject]@{ Code = -1; Out = ''; Err = 'timeout'; TimedOut = $true }
    }
    $p.WaitForExit()
    return [pscustomobject]@{ Code = $p.ExitCode; Out = $o.Result; Err = $e.Result; TimedOut = $false }
}

function Adb-Run {
    param([string[]]$Argv, [int]$TimeoutSec = 120)
    $full = @()
    if ($script:Serial) { $full += @('-s', $script:Serial) }
    $full += $Argv
    Write-Log ('$ adb ' + ($full -join ' '))
    $r = Invoke-Exe $script:Adb $full $TimeoutSec
    $r.Out = $r.Out -replace "`r", ''
    $r.Err = $r.Err -replace "`r", ''
    Write-Log ('  rc=' + $r.Code + ' out=' + (($r.Out + $r.Err).Trim()))
    return $r
}

function Sh {
    param([string]$Cmd, [int]$TimeoutSec = 120)
    $r = Adb-Run @('shell', $Cmd) $TimeoutSec
    if ($r.TimedOut) { return '__TIMEOUT__' }
    # adb 的报错走 stderr；只在 stdout 空时才透传，避免污染正常命令的输出
    if ($r.Out.Trim() -eq '' -and $r.Err.Trim() -ne '') { return $r.Err.Trim() }
    return ($r.Out.Trim())
}

function Test-AdbError([string]$s) {
    if ($null -eq $s) { return $true }
    if ($s -eq '__TIMEOUT__') { return $true }
    return [bool]($s -match '^(error|adb): ' -or $s -match 'no devices/emulators|device offline|device unauthorized')
}

function Adb-Install {
    param([string]$Apk, [int]$TimeoutSec = 300)
    return (Adb-Run @('install', '-r', '-g', $Apk) $TimeoutSec)
}

# ------------------------------------------------------------------ 设备
function Get-DeviceList {
    $r = Invoke-Exe $script:Adb @('devices') 30
    $list = @()
    foreach ($ln in ($r.Out -split "`r?`n")) {
        if ($ln -match '^\s*(\S+)\s+(device|unauthorized|offline|recovery|sideload)\s*$') {
            $list += [pscustomobject]@{ Serial = $Matches[1]; State = $Matches[2] }
        }
    }
    return $list
}

function Reset-AdbServer {
    Write-Log 'restart adb server'
    [void](Invoke-Exe $script:Adb @('kill-server') 30)
    Start-Sleep -Milliseconds 800
    [void](Invoke-Exe $script:Adb @('start-server') 30)
    Start-Sleep -Milliseconds 800
}

# ------------------------------------------------------------------ 模块补丁
function Patch-Module {
    param([string]$InKo, [string]$KsFile, [string]$OutKo)

    $bytes = [System.IO.File]::ReadAllBytes($InKo)
    if ($bytes.Length -lt 64 -or $bytes[0] -ne 0x7F -or $bytes[4] -ne 2) {
        throw "$InKo 不是 ELF64 文件"
    }

    # --- 1) __ubsan_handle_cfi_check_fail_abort 改名：这颗内核只有不带 _abort 的版本
    $latin1 = [System.Text.Encoding]::GetEncoding(28591)
    $text = $latin1.GetString($bytes)
    $old = '__ubsan_handle_cfi_check_fail_abort'
    $new = '__ubsan_handle_cfi_check_fail'
    $renamed = 0
    $pos = 0
    while (($pos = $text.IndexOf($old, $pos)) -ge 0) {
        $nb = [System.Text.Encoding]::ASCII.GetBytes($new)
        [Array]::Copy($nb, 0, $bytes, $pos, $nb.Length)
        for ($k = $nb.Length; $k -lt $old.Length; $k++) { $bytes[$pos + $k] = 0 }
        $renamed++
        $pos += $old.Length
    }

    # --- 2) 段表
    $shoff = [int][BitConverter]::ToUInt64($bytes, 0x28)
    $shentsize = [int][BitConverter]::ToUInt16($bytes, 0x3A)
    $shnum = [int][BitConverter]::ToUInt16($bytes, 0x3C)
    $shstrndx = [int][BitConverter]::ToUInt16($bytes, 0x3E)

    $shstrOff = [int][BitConverter]::ToUInt64($bytes, $shoff + $shstrndx * $shentsize + 0x18)
    $shstrSize = [int][BitConverter]::ToUInt64($bytes, $shoff + $shstrndx * $shentsize + 0x20)
    $shstr = $latin1.GetString($bytes, $shstrOff, $shstrSize)

    $symOff = -1; $symSize = 0; $symEnt = 24
    $strOff = -1; $strSize = 0
    for ($i = 0; $i -lt $shnum; $i++) {
        $b = $shoff + $i * $shentsize
        $nmOff = [int][BitConverter]::ToUInt32($bytes, $b)
        if ($nmOff -le 0 -or $nmOff -ge $shstr.Length) { continue }
        $end = $shstr.IndexOf([char]0, $nmOff)
        if ($end -lt 0) { continue }
        $nm = $shstr.Substring($nmOff, $end - $nmOff)
        if ($nm -eq '.symtab') {
            $symOff = [int][BitConverter]::ToUInt64($bytes, $b + 0x18)
            $symSize = [int][BitConverter]::ToUInt64($bytes, $b + 0x20)
            $ent = [int][BitConverter]::ToUInt64($bytes, $b + 0x38)
            if ($ent -gt 0) { $symEnt = $ent }
        }
        elseif ($nm -eq '.strtab') {
            $strOff = [int][BitConverter]::ToUInt64($bytes, $b + 0x18)
            $strSize = [int][BitConverter]::ToUInt64($bytes, $b + 0x20)
        }
    }
    if ($symOff -lt 0 -or $strOff -lt 0) { throw '找不到 .symtab / .strtab（模块被 strip 掉了符号表？）' }

    $strs = $latin1.GetString($bytes, $strOff, $strSize)

    # --- 3) 收集未定义符号
    $symCount = [int]($symSize / $symEnt)
    $undefIdx = New-Object 'System.Collections.Generic.List[int]'
    $undefName = @{}
    $want = @{}
    for ($n = 0; $n -lt $symCount; $n++) {
        $b = $symOff + $n * $symEnt
        $nmOff = [int][BitConverter]::ToUInt32($bytes, $b)
        $shndx = [int][BitConverter]::ToUInt16($bytes, $b + 6)
        if ($shndx -ne 0 -or $nmOff -eq 0) { continue }
        $end = $strs.IndexOf([char]0, $nmOff)
        if ($end -lt 0) { $end = $strs.Length }
        $nm = $strs.Substring($nmOff, $end - $nmOff)
        $undefIdx.Add($n)
        $undefName[$n] = $nm
        $want[$nm] = $true
    }
    if ($undefIdx.Count -eq 0) {
        return [pscustomobject]@{ Renamed = $renamed; Undef = 0; Resolved = 0; Missing = @(); Wrote = 0 }
    }

    # --- 4) 从 kallsyms 里取地址（首次出现优先，别名同址）
    $addr = @{}
    $hit = 0
    $need = $want.Count
    $lines = [System.IO.File]::ReadAllLines($KsFile)
    foreach ($ln in $lines) {
        if ($ln.Length -lt 6) { continue }
        $s1 = $ln.IndexOf(' ')
        if ($s1 -le 0) { continue }
        $s2 = $ln.IndexOf(' ', $s1 + 1)
        if ($s2 -lt 0) { continue }
        $s3 = $ln.IndexOf(' ', $s2 + 1)
        if ($s3 -gt 0) { $nm = $ln.Substring($s2 + 1, $s3 - $s2 - 1) } else { $nm = $ln.Substring($s2 + 1) }
        if ($nm.Length -eq 0) { continue }
        if (-not $want.ContainsKey($nm)) { continue }
        if ($addr.ContainsKey($nm)) { continue }
        $hex = $ln.Substring(0, $s1)
        $v = [uint64]0
        if (-not [uint64]::TryParse($hex, [System.Globalization.NumberStyles]::HexNumber, $null, [ref]$v)) { continue }
        if ($v -eq 0) { continue }
        $addr[$nm] = $v
        $hit++
        if ($hit -ge $need) { break }
    }

    # --- 5) 把未定义符号改写成 SHN_ABS + 运行时地址
    $resolved = 0
    $missing = New-Object 'System.Collections.Generic.List[string]'
    foreach ($n in $undefIdx) {
        $nm = $undefName[$n]
        if (-not $addr.ContainsKey($nm)) { $missing.Add($nm); continue }
        $b = $symOff + $n * $symEnt
        $bytes[$b + 6] = 0xF1
        $bytes[$b + 7] = 0xFF
        $v = [BitConverter]::GetBytes([uint64]$addr[$nm])
        [Array]::Copy($v, 0, $bytes, $b + 8, 8)
        $resolved++
    }

    [System.IO.File]::WriteAllBytes($OutKo, $bytes)
    return [pscustomobject]@{
        Renamed = $renamed
        Undef = $undefIdx.Count
        Resolved = $resolved
        Missing = $missing
        Wrote = $bytes.Length
    }
}

# ------------------------------------------------------------------ 工具
function Local-Md5([string]$p) { return (Get-FileHash -Path $p -Algorithm MD5).Hash.ToLower() }
function Dev-Md5([string]$remote) {
    $o = Sh ("md5sum '" + $remote + "' 2>/dev/null") 60
    if ($o -eq '__TIMEOUT__' -or $o.Length -lt 32) { return '' }
    return $o.Split(' ')[0].Trim().ToLower()
}

function Push-Payload([string]$local, [string]$remote, [bool]$exec) {
    $src = Join-Path $script:Payload $local
    if (-not (Test-Path $src)) { Die ("工具包不完整：缺少 payload\" + $local) }
    $want = Local-Md5 $src
    if ((Dev-Md5 $remote) -eq $want) {
        if ($exec) { [void](Sh ("chmod 755 '" + $remote + "'") 30) }
        Info ("$local 已在设备上，跳过")
        return
    }
    $r = Adb-Run @('push', $src, $remote) 300
    if ($r.Code -ne 0) { Die ("推送 $local 失败：" + ($r.Err + $r.Out).Trim()) }
    if ((Dev-Md5 $remote) -ne $want) { Die ("$local 推送后校验不一致（USB 不稳定？）") }
    if ($exec) { [void](Sh ("chmod 755 '" + $remote + "'") 30) }
    Ok ("$local -> $remote")
}

# ------------------------------------------------------------------ 主流程
function Show-Banner {
    Write-Host ''
    Write-Host '  ┌──────────────────────────────────────────────┐' -ForegroundColor DarkCyan
    Write-Host '  │   Magic5 一键提权   PGT-AN00 / ACK 5.15.180  │' -ForegroundColor DarkCyan
    Write-Host '  └──────────────────────────────────────────────┘' -ForegroundColor DarkCyan
}

function Show-Status {
    Step '读取设备状态'
    $model = Sh 'getprop ro.product.model'
    $rel = Sh 'uname -r'
    $sec = Sh 'getenforce'
    $mods = Sh 'grep kernelsu /proc/modules'
    $pkg = Sh "pm list packages 2>/dev/null | grep -i resukisu"
    Info ("机型      " + $model.Trim())
    Info ("内核      " + $rel.Trim())
    Info ("SELinux   " + $sec.Trim())
    if ($mods -match 'Live') { Ok ('KSU 模块已加载：' + $mods.Trim()) }
    elseif ($mods -eq '' ) { Info '  KSU 模块未加载' }
    else { Warn ('KSU 模块状态异常：' + $mods.Trim()) }
    if ($pkg -match 'resukisu') { Ok ('管理器已安装：' + $pkg.Trim()) } else { Info '管理器未安装' }
    $u = Sh '/data/local/tmp/su -c "id -u" 2>/dev/null'
    if ($u.Trim() -eq '0') { Ok '临时 root 仍在（helper 存活）' } else { Info '临时 root 未启动' }
}

# ---- 1
function Step-Device {
    Step '连接设备'
    if (-not (Test-Path $script:Adb)) { Die ('找不到 tools\adb.exe，工具包被拆开了？') }

    $devs = @(Get-DeviceList)
    $ok = @($devs | Where-Object { $_.State -eq 'device' })
    if ($ok.Count -eq 0) {
        # 荣耀自带的 hwtransport.exe 会抢占 5037 端口，导致 adb 看不到设备
        $hw = Get-Process -Name hwtransport -ErrorAction SilentlyContinue
        if ($hw) { Warn '检测到 hwtransport.exe 占用 adb 端口，正在结束它'; $hw | Stop-Process -Force -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 800 }
        Reset-AdbServer
        $devs = @(Get-DeviceList)
        $ok = @($devs | Where-Object { $_.State -eq 'device' })
    }

    $unauth = @($devs | Where-Object { $_.State -eq 'unauthorized' })
    if ($ok.Count -eq 0 -and $unauth.Count -gt 0) {
        Die ("设备已连上但未授权。`n        请在手机上解锁屏幕，点弹窗里的「允许 USB 调试」，并勾选「一律允许」。")
    }
    if ($ok.Count -eq 0) {
        Die ("没找到设备。请依次确认：`n" +
             "        1) 数据线接好，手机解锁亮屏；`n" +
             "        2) 设置 → 系统 → 开发者选项 → USB 调试 已开；`n" +
             "        3) 下拉通知栏把「USB 用途」改成「传输文件 / MTP」；`n" +
             "        4) 电脑没装 ADB 驱动的话，装 usb_driver 目录里的驱动后重插。`n" +
             "        改完重跑本程序即可。")
    }
    $script:Serial = $ok[0].Serial
    if ($ok.Count -gt 1) { Warn ("检测到 " + $ok.Count + " 台设备，使用第一台：" + $script:Serial) }
    Ok ('已连接 ' + $script:Serial)
}

# ---- 2
function Step-Check {
    Step '核对机型与内核'
    $model = (Sh 'getprop ro.product.model').Trim()
    $rel = (Sh 'uname -r').Trim()
    $android = (Sh 'getprop ro.build.version.release').Trim()
    Info ("机型    " + $model + "   Android " + $android)
    Info ("内核    " + $rel)

    if ($model -notlike "*$MODEL_WANT*") {
        if (-not $Force) { Die ("这不是 " + $MODEL_WANT + "（荣耀 Magic5）。`n        载荷与这个型号的内核绑定，换机型会直接 panic。确实要继续请加 -Force。") }
        Warn "机型不匹配，-Force 已指定，继续"
    }
    if ($rel -ne $KERNEL_WANT) {
        if (-not $Force) {
            Die ("内核版本不匹配。`n        需要：" + $KERNEL_WANT + "`n        当前：" + $rel + "`n" +
                 "        模块里的结构体偏移、KASLR 常量都是对这个内核编译的，`n" +
                 "        硬加载会立刻 oops 并重启。系统更新过就必须重新编译模块。")
        }
        Warn "内核不匹配，-Force 已指定，后果自负"
    } else {
        Ok '机型与内核匹配'
    }
}

# ---- 3
function Step-Push {
    Step '推送载荷'
    Push-Payload 'magic5-root.so' '/data/local/tmp/magic5-root.so' $true
    Push-Payload 'profile_175.bin' '/data/local/tmp/profile_175.bin' $false
    Push-Payload 'kmsgsync' '/data/local/tmp/kmsgsync' $true
    Push-Payload 'kit-root.sh' '/data/local/tmp/kit-root.sh' $false
    Push-Payload 'kit-load.sh' '/data/local/tmp/kit-load.sh' $false
}

# ---- 4
function Step-Root {
    Step '取临时 root（约 20-60 秒，可能触发一次内核重启）'
    $out = Sh ('sh /data/local/tmp/kit-root.sh ' + $ZERO_ADDR) 300
    if ($out -eq '__TIMEOUT__') { Die '设备端脚本超时。拔插数据线后重跑；若手机自动重启，说明这次 oops 了，重启完再跑一次即可。' }

    $kv = @{}
    foreach ($ln in ($out -split "`n")) {
        if ($ln -match '^([a-z_]+)=(.*)$') { $kv[$Matches[1]] = $Matches[2].Trim() }
    }
    $uid = $kv['uid']
    if ($kv.ContainsKey('err')) {
        Die ('设备端准备载荷失败：' + $kv['err'] + '。多半是上次提权留下的文件 SELinux 标签坏了，重启手机再跑一次。')
    }
    if ($null -eq $uid) { Write-Host $out; Die '设备端脚本没有返回预期输出' }

    if ($uid -ne '0') {
        $lg = $kv['log']
        Warn "没有拿到 root（uid=$uid），载荷日志末尾："
        if ($lg) { Write-Host ((Sh ("tail -n 15 '" + $lg + "'") 60)) -ForegroundColor DarkGray }
        Die '提权没成功。多数情况是这次运气不好（这个漏洞有概率失败），直接重跑本程序；连续两次失败请重启手机再试。'
    }
    Ok ('uid=0，_text=' + $kv['text'])
    Info ('kallsyms 行数 ' + $kv['ks_lines'] + '    sig_enforce=' + $kv['sig'])
    if ($kv['sig'] -notin @('0', 'N', 'n')) { Warn ('sig_enforce=' + $kv['sig'] + '，模块可能被验签拒绝') }
    return $kv
}

# ---- 5
function Step-Patch([hashtable]$kv) {
    Step '导出符号并按本次 KASLR 打补丁'
    $ksRemote = $kv['ks']
    $ksLocal = Join-Path $script:Work 'ks.txt'
    $r = Adb-Run @('pull', $ksRemote, $ksLocal) 180
    if ($r.Code -ne 0 -or -not (Test-Path $ksLocal)) { Die '拉取 kallsyms 失败' }
    $lines = [System.IO.File]::ReadAllLines($ksLocal).Length
    if ($lines -lt 10000) { Die ("kallsyms 只有 " + $lines + " 行，像是空文件（root 窗口太短）") }
    Ok ("kallsyms " + $lines + " 行")

    $srcKo = Join-Path $script:Payload $MOD_NAME
    if ($Module) {
        if (Test-Path $Module) { $srcKo = (Resolve-Path $Module).Path }
        else { Die ('指定的模块不存在：' + $Module) }
    }
    if (-not (Test-Path $srcKo)) { Die ('工具包不完整：缺少 payload\' + $MOD_NAME) }
    $outKo = Join-Path $script:Work 'ksu-ready.ko'
    $res = Patch-Module -InKo $srcKo -KsFile $ksLocal -OutKo $outKo

    Info ("未定义符号 " + $res.Undef + " 个，ubsan 改名 " + $res.Renamed + " 处")
    if ($res.Missing.Count -gt 0) {
        # 已导出的符号本来就不需要 kallsyms，交给内核 loader 按 __ksymtab 解析
        Warn ("有 " + $res.Missing.Count + " 个符号不在 kallsyms 里，留给内核自己解析：" + (($res.Missing | Select-Object -First 6) -join ', '))
    }
    Ok ("已把 " + $res.Resolved + " 个符号改写成绝对地址")
    return $outKo
}

# ---- 6
function Step-Load([string]$ko) {
    Step '装载 KSU 模块'
    $cur = Sh 'grep kernelsu /proc/modules' 30
    if (Test-AdbError $cur) { Die '读不到设备状态，USB 可能掉了（拔插数据线后重跑）' }
    if ($cur -match 'Live') { Ok '模块已经在跑了，跳过装载'; return $true }
    if ($cur.Trim() -ne '') {
        Warn ('模块名被占用但没运行起来：' + $cur.Trim())
        Warn '必须先重启手机，rmmod 会被内核拒绝（EAGAIN）'
        return $false
    }

    $remote = $DEV_MOD
    $r = Adb-Run @('push', $ko, $remote) 300
    if ($r.Code -ne 0) { Die '推送打过补丁的模块失败' }
    [void](Sh ("chmod 644 '" + $remote + "'") 30)

    $out = Sh ("sh /data/local/tmp/kit-load.sh " + $remote) 60
    if (Test-AdbError $out) { Die '装载脚本没跑起来，USB 掉了' }
    $kmlog = ''
    if ($out -match 'kmlog=(\S+)') { $kmlog = $Matches[1] }

    $live = $false
    for ($i = 1; $i -le 40; $i++) {
        Start-Sleep -Seconds 2
        $m = Sh 'grep kernelsu /proc/modules' 30
        if (Test-AdbError $m) {
            Warn '设备掉线了（多半是 oops 后自动重启）'
            return $false
        }
        if ($m -match 'Live') { $live = $true; break }
        $done = Sh 'cat /data/local/tmp/insmod.rc 2>/dev/null' 20
        if ($done -match 'rc=(\d+)' -and $Matches[1] -ne '0') {
            Warn ('insmod 返回 ' + $Matches[1])
            break
        }
    }

    if (-not $live) {
        if ($kmlog) {
            Warn '内核日志末尾：'
            Write-Host ((Sh ("tail -n 20 '" + $kmlog + "'") 60)) -ForegroundColor DarkGray
        }
        $why = Sh "dmesg | grep -iE 'kernelsu: |Unknown symbol|version magic|module verification|disagrees about version' | tail -6" 30
        if ($why -and -not (Test-AdbError $why)) {
            Warn '内核给出的原因：'
            Write-Host $why -ForegroundColor DarkGray
        }
        return $false
    }
    Ok ('模块已加载：' + (Sh 'grep kernelsu /proc/modules').Trim())
    return $true
}

# ---- 7
function Step-Verify {
    Step '验证'
    $sec = (Sh 'getenforce').Trim()
    Info ('SELinux  ' + $sec)
    if ($sec -eq 'Enforcing') { Warn 'SELinux 是 Enforcing：模块没生效（策略注入会破坏网络，所以载荷会保持 permissive）' }

    $pkg = (Sh "pm list packages 2>/dev/null | grep -i resukisu").Trim()
    if (-not $pkg) {
        $apk = Join-Path $script:Payload 'ReSukiSU-4.2.0-rc3.apk'
        if (Test-Path $apk) {
            Warn '没装管理器，正在安装 ReSukiSU（4.2.0-rc3）...'
            $r = Adb-Install $apk 300
            if ($r.Code -eq 0) {
                Ok '管理器已安装'
                Warn '注意：内置的是官方 rc3 正式版（uapi 4），内核是 uapi 6，'
                Warn '      管理器可能显示「需要更新内核」红条，但 root 功能照常可用。'
            }
            else { Warn ('安装失败：' + ($r.Err + $r.Out).Trim()); Warn ('可以手动装：payload\' + (Split-Path $apk -Leaf)) }
        } else {
            Warn '没装管理器，且工具包里没有 apk'
        }
    } else {
        Ok ('管理器 ' + $pkg)
    }

    $apkver = (Sh 'dumpsys package com.resukisu.resukisu 2>/dev/null | grep -m1 versionName').Trim()
    if ($apkver) { Info ($apkver -replace '\s+', ' ') }

    # ksud 装在 /data/adb 下，shell 域读不到，必须借临时 root 跑。
    # ksud -V 会打印 (uapi: 6)，正好用来核对内核与用户态版本是否配套。
    $ksv = Sh "/data/local/tmp/su -c '/data/adb/ksu/bin/ksud -V' 2>/dev/null" 30
    if ($ksv -match 'uapi:\s*(\d+)') {
        Ok ('ksud ' + $ksv.Trim())
        if ($Matches[1] -ne '6') {
            Warn ('ksud 的 uapi=' + $Matches[1] + '，内核是 6，管理器可能显示「需要更新内核」')
        }
    } else {
        Info 'ksud 暂不可读（管理器首次启动会自动安装；临时 root 也可能已失效）'
    }
}

function Show-Done {
    Write-Host ''
    Write-Host '  ┌──────────────────────────────────────────────┐' -ForegroundColor Green
    Write-Host '  │  完成：KSU 已接管，root 可用                  │' -ForegroundColor Green
    Write-Host '  └──────────────────────────────────────────────┘' -ForegroundColor Green
    Write-Host ''
    Write-Host '  · 打开手机上的 ReSukiSU / BakaSU，应显示「工作中 · LKM」' -ForegroundColor Gray
    Write-Host '  · 给 App 授权：管理器 → 超级用户 → 勾选目标应用' -ForegroundColor Gray
    Write-Host '  · 电脑上临时 root：adb shell /data/local/tmp/su -c "id"' -ForegroundColor Gray
    Write-Host '  · /system/bin/su 不存在是正常的，KSU 只对已授权的 uid 生效' -ForegroundColor Gray
    Write-Host '  · 重启后需要重跑本程序（没有改 boot，属于临时 root）' -ForegroundColor Gray
    Write-Host ''
}

# ------------------------------------------------------------------ 入口
try {
    if (-not (Test-Path $script:Work)) { New-Item -ItemType Directory -Path $script:Work -Force | Out-Null }
    Write-Log ('=== kit start ' + (Get-Date) + ' args=' + ($PSBoundParameters.Keys -join ','))

    Show-Banner

    if ($Status) {
        $script:StepAll = 2
        Step-Device
        Show-Status
        exit 0
    }

    if ($RootOnly -or $Shell) { $script:StepAll = 4 }

    Step-Device
    Step-Check

    # 已经有模块在跑就不用重新走一遍漏洞
    $liveNow = (Sh 'grep kernelsu /proc/modules' 30)
    if ($liveNow -match 'Live') {
        Ok 'KSU 模块已在运行，跳过提权与装载'
        $script:StepAll = 1
        $script:StepNo = 0
        Step-Verify
        Show-Done
        exit 0
    }

    Step-Push
    $kv = Step-Root

    if ($RootOnly -or $Shell) {
        Write-Host ''
        Ok '临时 root 已就绪'
        Info '设备端命令：adb shell /data/local/tmp/su -c "id"'
        if ($Shell) {
            Write-Host ''
            Write-Host '  进入 root shell（输入 exit 返回）' -ForegroundColor Gray
            $a = @()
            if ($script:Serial) { $a += @('-s', $script:Serial) }
            $a += @('shell', '-t', '/data/local/tmp/su')
            & $script:Adb @a
        }
        exit 0
    }

    $ko = Step-Patch $kv
    $loaded = Step-Load $ko
    if (-not $loaded) {
        Die ('模块没能加载。上面有内核给的原因；若是 insmod 返回非 0，多半是这次 root 窗口里`n' +
             '        sig_enforce 没清干净 —— 重启手机后重跑一次通常就好。日志在 kit-*.log。')
    }
    Step-Verify
    Show-Done
    exit 0
}
catch {
    Write-Host ''
    Write-Host ('  [异常] ' + $_.Exception.Message) -ForegroundColor Red
    Write-Log ('EXCEPTION ' + $_.Exception.ToString())
    Write-Host ('  详细日志：' + $script:LogFile) -ForegroundColor DarkGray
    exit 1
}
