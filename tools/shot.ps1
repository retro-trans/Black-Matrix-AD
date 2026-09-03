# Capture the redream window to a PNG.
#
# Having a picture of the running game closes the loop for text work: poke a
# value in memory, take a shot, see what moved.
#
#   powershell -ExecutionPolicy Bypass -File tools\shot.ps1 -Out shot.png

param(
    [string]$Out = "E:\Projects\Black Matrix AD\extracted\shot.png",
    [string]$ProcName = "redream"
)

Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;

public class Win {
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left, Top, Right, Bottom; }

    [DllImport("user32.dll")]
    public static extern bool GetClientRect(IntPtr h, out RECT r);

    [DllImport("user32.dll")]
    public static extern bool ClientToScreen(IntPtr h, ref System.Drawing.Point p);

    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr h);

    [DllImport("user32.dll")]
    public static extern bool IsIconic(IntPtr h);

    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr h, int cmd);
}
'@ -ReferencedAssemblies System.Drawing

$proc = Get-Process | Where-Object {
    $_.ProcessName -like "*$ProcName*" -and $_.MainWindowHandle -ne 0
} | Select-Object -First 1
if (-not $proc) { Write-Output "no $ProcName window found"; exit 1 }

$h = $proc.MainWindowHandle
if ([Win]::IsIconic($h)) { [Win]::ShowWindow($h, 9) | Out-Null; Start-Sleep -Milliseconds 400 }

$r = New-Object Win+RECT
[Win]::GetClientRect($h, [ref]$r) | Out-Null
$w = $r.Right - $r.Left
$hgt = $r.Bottom - $r.Top
if ($w -le 0 -or $hgt -le 0) { Write-Output "window has no client area"; exit 1 }

$origin = New-Object System.Drawing.Point(0, 0)
[Win]::ClientToScreen($h, [ref]$origin) | Out-Null

$bmp = New-Object System.Drawing.Bitmap($w, $hgt)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($origin.X, $origin.Y, 0, 0, (New-Object System.Drawing.Size($w, $hgt)))
$g.Dispose()

$dir = Split-Path -Parent $Out
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Output "wrote $Out ($w x $hgt) from pid $($proc.Id)"
