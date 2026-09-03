# Boot the patched disc in redream and drive it to the Config screen.
#
# The Config screen is the reference for text work: its help line is a
# known 11-character record in a uniform character grid, so any change in
# glyph spacing shows up immediately.
#
#   powershell -ExecutionPolicy Bypass -File tools\runcfg.ps1 -Out build\shot.png
#
# Two things this has to get right, both learned the hard way:
#   * redream must be started with -NoNewWindow from here or the process
#     exits immediately;
#   * synthetic keys go to whatever window has focus, so the script refuses
#     to send any unless SetForegroundWindow actually took.
#
# redream's keyboard profile: START=space, A=l, B=p, dpad up/down/left/right
# = t/g/f/h.  The title screen needs START twice: once to break out of the
# attract movie, once for "Press Start Button".
#
# The title menu keeps the cursor wherever it was last left, so a fixed number
# of downs lands somewhere different depending on what happened last run - it
# is easy to start a New Game by accident.  The menu *clamps* at the top
# rather than wrapping, so three ups always reach "New Game" and two downs
# from there always reach "Config".

param(
    [string]$Cue = "E:\Projects\Black Matrix AD\build\disc\Black-Matrix Advanced (Japan) (Disc 1).cue",
    [string]$Out = "E:\Projects\Black Matrix AD\build\shot.png",
    [string]$Exe = "M:\Program\Redream\redream.exe",
    [int]$BootSeconds = 24,
    [switch]$KeepRunning
)

Add-Type @'
using System;
using System.Runtime.InteropServices;
public class Drive {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
  [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, IntPtr extra);
  [DllImport("user32.dll")] public static extern uint MapVirtualKey(uint code, uint type);
  public static void Tap(byte vk) {
    byte sc = (byte)MapVirtualKey(vk, 0);
    keybd_event(vk, sc, 0x0008, IntPtr.Zero);
    System.Threading.Thread.Sleep(70);
    keybd_event(vk, sc, 0x0008 | 0x0002, IntPtr.Zero);
  }
}
'@

Stop-Process -Name redream -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

$tmp = [System.IO.Path]::GetTempFileName()
Start-Process -FilePath $Exe -ArgumentList "`"$Cue`"" -NoNewWindow `
    -RedirectStandardOutput $tmp -RedirectStandardError "$tmp.err" | Out-Null
Start-Sleep -Seconds $BootSeconds

$p = Get-Process redream -ErrorAction SilentlyContinue |
     Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if (-not $p) { Write-Output "redream did not start"; exit 1 }

[Drive]::ShowWindow($p.MainWindowHandle, 9) | Out-Null
[Drive]::SetForegroundWindow($p.MainWindowHandle) | Out-Null
Start-Sleep -Milliseconds 900
if ([Drive]::GetForegroundWindow() -ne $p.MainWindowHandle) {
    Write-Output "could not focus redream - refusing to send keys somewhere else"
    exit 1
}

[Drive]::Tap(0x20); Start-Sleep -Milliseconds 1200     # skip the attract movie
[Drive]::Tap(0x20); Start-Sleep -Milliseconds 1500     # "Press Start Button"
1..3 | ForEach-Object { [Drive]::Tap(0x54); Start-Sleep -Milliseconds 300 }  # up, clamps
[Drive]::Tap(0x47); Start-Sleep -Milliseconds 400      # down
[Drive]::Tap(0x47); Start-Sleep -Milliseconds 400      # down -> Config
[Drive]::Tap(0x4C); Start-Sleep -Seconds 3             # A

& powershell -ExecutionPolicy Bypass -File "E:\Projects\Black Matrix AD\tools\shot2.ps1" -Out $Out
if (-not $KeepRunning) { Write-Output "redream left running (pid $($p.Id))" }
