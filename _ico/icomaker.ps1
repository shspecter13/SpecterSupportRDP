<#
    .SYNOPSIS
        Generates a 100% Windows Resource Compiler (rc.exe) compliant multi-layer .ico file.
#>

Add-Type -AssemblyName System.Drawing

$pngPath = Resolve-Path ".\scripts\Common\ico_draft.png"
$icoPath = Join-Path -Path (Split-Path $pngPath) -ChildPath "app_icon.ico"

$sizes = @(16, 24, 32, 48, 64, 128, 256)
$sourceBmp = [System.Drawing.Bitmap]::FromFile($pngPath)

# --- ADD THIS LINE: Automatically converts pure white (#FFFFFF) to 100% alpha transparency ---
$sourceBmp.MakeTransparent([System.Drawing.Color]::White)

$iconEntries = [System.Collections.Generic.List[PSCustomObject]]::new()

foreach ( $size in $sizes ) {
    # 1. High-Quality Bicubic Resize
    $resized = [System.Drawing.Bitmap]::new($size, $size, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($resized)
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g.SmoothingMode     = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
    $g.PixelOffsetMode   = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $g.DrawImage($sourceBmp, 0, 0, $size, $size)
    $g.Dispose()

    # 2. Extract Raw 32-bit BGRA Pixels (Bottom-Up format for DIB)
    $bmpData = $resized.LockBits(
        [System.Drawing.Rectangle]::new(0, 0, $size, $size),
        [System.Drawing.Imaging.ImageLockMode]::ReadOnly,
        [System.Drawing.Imaging.PixelFormat]::Format32bppArgb
    )

    $stride = $bmpData.Stride
    $pixelBytes = [byte[]]::new($stride * $size)
    [System.Runtime.InteropServices.Marshal]::Copy($bmpData.Scan0, $pixelBytes, 0, $pixelBytes.Length)
    $resized.UnlockBits($bmpData)
    $resized.Dispose()

    # 3. Construct Standard BITMAPINFOHEADER (40 Bytes)
    $ms = [System.IO.MemoryStream]::new()
    $bw = [System.IO.BinaryWriter]::new($ms)

    $biSizeImage = $size * $size * 4
    $maskRowBytes = [math]::Ceiling($size / 32.0) * 4
    $maskSize = $maskRowBytes * $size

    $bw.Write([uint32]40)              # biSize (40 bytes)
    $bw.Write([int32]$size)            # biWidth
    $bw.Write([int32]($size * 2))      # biHeight (Doubled for XOR + AND masks)
    $bw.Write([uint16]1)               # biPlanes
    $bw.Write([uint16]32)              # biBitCount (32-bit BGRA)
    $bw.Write([uint32]0)               # biCompression (BI_RGB)
    $bw.Write([uint32]($biSizeImage + $maskSize)) # biSizeImage
    $bw.Write([int32]0)                # biXPelsPerMeter
    $bw.Write([int32]0)                # biYPelsPerMeter
    $bw.Write([uint32]0)               # biClrUsed
    $bw.Write([uint32]0)               # biClrImportant

    # 4. Write Bottom-Up Color Pixel Rows
    for ( $y = $size - 1; $y -ge 0; $y-- ) {
        $rowOffset = $y * $stride
        $bw.Write($pixelBytes, $rowOffset, $stride)
    }

    # 5. Write 1-bit AND Transparency Mask (All 0s for 32bpp ARGB)
    $andMask = [byte[]]::new($maskSize)
    $bw.Write($andMask)

    $payload = $ms.ToArray()
    $bw.Close()
    $ms.Close()

    $iconEntries.Add([PSCustomObject]@{
        Width   = $size
        Height  = $size
        Payload = $payload
    })
}

$sourceBmp.Dispose()

# 6. Write Full Master .ICO File
$fs = [System.IO.File]::Create($icoPath)
$masterWriter = [System.IO.BinaryWriter]::new($fs)

# ICONDIR Header
$masterWriter.Write([uint16]0)                  # Reserved
$masterWriter.Write([uint16]1)                  # Icon Type
$masterWriter.Write([uint16]$iconEntries.Count) # Count

# Header (6) + (16 * Entries)
$dataOffset = 6 + ($iconEntries.Count * 16)

# Write ICONDIRENTRY Table
foreach ( $entry in $iconEntries ) {
    $w = if ( $entry.Width -ge 256 ) { 0 } else { $entry.Width }
    $h = if ( $entry.Height -ge 256 ) { 0 } else { $entry.Height }

    $masterWriter.Write([byte]$w)
    $masterWriter.Write([byte]$h)
    $masterWriter.Write([byte]0)                    # Palette
    $masterWriter.Write([byte]0)                    # Reserved
    $masterWriter.Write([uint16]1)                  # Planes
    $masterWriter.Write([uint16]32)                 # BitCount
    $masterWriter.Write([uint32]$entry.Payload.Length)
    $masterWriter.Write([uint32]$dataOffset)

    $dataOffset += $entry.Payload.Length
}

# Write All Payloads
foreach ( $entry in $iconEntries ) {
    $masterWriter.Write($entry.Payload)
}

$masterWriter.Flush()
$masterWriter.Close()
$fs.Close()

Write-Host "`n[SUCCESS] Generated 100% compliant Windows RC icon: $icoPath" -ForegroundColor Green