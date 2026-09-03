# Capture the redream window without stealing focus.
#
# shot.ps1 copies from the screen, so anything overlapping redream ends up in
# the picture instead - and SetForegroundWindow silently fails while the user
# is typing elsewhere.  PrintWindow with PW_RENDERFULLCONTENT asks the window
# to draw itself into a bitmap, which works for occluded OpenGL windows.
#
#   powershell -ExecutionPolicy Bypass -File tools\shot2.ps1 -Out build\shot.png
#
# Falls back to nothing: if the result is a solid colour the driver refused,
# and the script says so rather than writing a black PNG.

param(
    [string]$Out = "E:\Projects\Black Matrix AD\build\shot.png",
    [string]$ProcName = "redream"
)

Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Drawing;
using System.Runtime.InteropServices;

public class Snap {
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left, Top, Right, Bottom; }

    [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint flags);

    public const uint RENDER_FULL_CONTENT = 0x00000002;

    public static Bitmap Grab(IntPtr hwnd) {
        RECT r;
        if (!GetClientRect(hwnd, out r)) return null;
        int w = r.Right - r.Left, h = r.Bottom - r.Top;
        if (w <= 0 || h <= 0) return null;
        Bitmap bmp = new Bitmap(w, h);
        using (Graphics g = Graphics.FromImage(bmp)) {
            IntPtr dc = g.GetHdc();
            bool ok = PrintWindow(hwnd, dc, RENDER_FULL_CONTENT);
            g.ReleaseHdc(dc);
            if (!ok) { bmp.Dispose(); return null; }
        }
        return bmp;
    }

    // A window that refused to render comes back a single flat colour.
    public static bool IsFlat(Bitmap b) {
        Color first = b.GetPixel(0, 0);
        int step = Math.Max(1, b.Width / 64);
        for (int y = 0; y < b.Height; y += step)
            for (int x = 0; x < b.Width; x += step)
                if (b.GetPixel(x, y) != first) return false;
        return true;
    }
}
'@ -ReferencedAssemblies System.Drawing

$proc = Get-Process | Where-Object {
    $_.ProcessName -like "*$ProcName*" -and $_.MainWindowHandle -ne 0
} | Select-Object -First 1
if (-not $proc) { Write-Output "no $ProcName window found"; exit 1 }

$bmp = [Snap]::Grab($proc.MainWindowHandle)
if ($null -eq $bmp) { Write-Output "PrintWindow failed"; exit 1 }
if ([Snap]::IsFlat($bmp)) {
    $bmp.Dispose()
    Write-Output "PrintWindow returned a blank frame - this window will not render offscreen"
    exit 1
}

$dir = Split-Path -Parent $Out
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
Write-Output "wrote $Out ($($bmp.Width) x $($bmp.Height)) from pid $($proc.Id)"
$bmp.Dispose()
