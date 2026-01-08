# Glasswing Installation Guide

## System Requirements

- **Windows:** 10 or 11 (64-bit)
- **macOS:** 10.15+ (Catalina or later)
- **Linux:** Ubuntu 20.04+ or equivalent

## Prerequisites

### Required Native Tools

Glasswing requires these native tools to be installed separately:

#### Windows

1. **ImageMagick** - Download from [imagemagick.org](https://imagemagick.org/script/download.php#windows)
   - Choose "ImageMagick-7.x.x-Q16-x64-dll.exe"
   - During installation, check "Add to PATH"

2. **ExifTool** - Download from [exiftool.org](https://exiftool.org/)
   - Extract exiftool(-k).exe and rename to exiftool.exe
   - Place in C:\Windows\ or add directory to PATH

#### macOS

```bash
brew install imagemagick exiftool
```

#### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install imagemagick libmagickwand-dev exiftool libexiv2-27
```

### Optional: IPFS Features

To use IPFS integration features:
- Install [IPFS Desktop](https://docs.ipfs.tech/install/ipfs-desktop/)
- Or install IPFS daemon and run: `ipfs daemon`

## Installation

### Windows

1. Download `glasswing-windows.exe` from the latest release
2. Double-click to run
3. If SmartScreen appears, click "More info" > "Run anyway"

### macOS

1. Download the appropriate file for your architecture:
   - **Intel Macs:** `glasswing-amd64.zip`
   - **Apple Silicon:** `glasswing-arm64.zip`
2. Extract the ZIP file
3. Move `glasswing.app` to Applications folder
4. Right-click `glasswing.app` and select "Open"
5. Click "Open" in the dialog (required first time due to Gatekeeper)

### Linux

1. Download `glasswing-linux` from the latest release
2. Make executable and run:

```bash
chmod +x glasswing-linux
./glasswing-linux
```

## Troubleshooting

### "ImageMagick not found"

Ensure ImageMagick is installed and in your PATH:

**Windows:** Run `magick --version` in Command Prompt
**macOS/Linux:** Run `convert --version` in Terminal

If not found:
- **Windows:** Reinstall ImageMagick and ensure "Add to PATH" is checked
- **macOS:** Run `brew install imagemagick`
- **Linux:** Run `sudo apt install imagemagick libmagickwand-dev`

### "ExifTool not found"

Ensure ExifTool is installed:

Run `exiftool -ver` in your terminal/command prompt

If not found:
- **Windows:** Download from https://exiftool.org/ and add to PATH
- **macOS:** Run `brew install exiftool`
- **Linux:** Run `sudo apt install exiftool`

### "IPFS features unavailable"

IPFS features require a running IPFS daemon at 127.0.0.1:5001.
These features are optional - the application will work without them.

To enable IPFS:
1. Install IPFS Desktop or IPFS daemon
2. Start the daemon
3. Restart Glasswing

### macOS "App is damaged" error

This occurs if you moved the app before opening it the first time.

**Solution:**
1. Delete the app
2. Re-extract from the ZIP file
3. Right-click > Open before moving it

### Windows SmartScreen Warning

This is normal for unsigned executables.

**Solution:**
1. Click "More info"
2. Click "Run anyway"

## Font Licensing Notice

This software includes OCR-A font, copyrighted by Monotype (1994).
Ensure you have appropriate licensing for commercial use.

## Support

For issues and questions:
- GitHub Issues: https://github.com/[your-repo]/glasswing/issues
- Documentation: https://github.com/[your-repo]/glasswing/blob/main/README.md
