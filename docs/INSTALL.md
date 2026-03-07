# Andromica Installation Guide

## System Requirements

- **Windows:** 10 or 11 (64-bit)
- **macOS:** 10.15+ (Catalina or later)
- **Linux:** Ubuntu 20.04+ or equivalent

## Prerequisites

### Required Native Tools

Andromica requires these native tools to be installed separately:

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

### Required for Media & Deployment: IPFS

IPFS is required for video embedding (encrypted video tokens are stored on IPFS) and all deployment features. Audio and markdown embedding work without IPFS since tokens are stored directly in PNG tEXt chunks.

- Install [IPFS Desktop](https://docs.ipfs.tech/install/ipfs-desktop/)
- Or install IPFS daemon and run: `ipfs daemon`
- Default API port: 5001, Gateway port: 8080

## Installation

### Windows

1. Download `andromica-windows.exe` from the latest release
2. Double-click to run
3. If SmartScreen appears, click "More info" > "Run anyway"

### macOS

1. Download `andromica-macos.zip` from the latest release
   - This is an ARM (Apple Silicon) build
   - Intel Macs can run it via Rosetta 2 (automatic, no extra setup)
2. Extract the ZIP file
3. Move `andromica.app` to Applications folder
4. Right-click `andromica.app` and select "Open"
5. Click "Open" in the dialog (required first time due to Gatekeeper)

### Linux

1. Download `andromica-linux` from the latest release
2. Make executable and run:

```bash
chmod +x andromica-linux
./andromica-linux
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
Basic image editing, audio embedding, and markdown embedding work without IPFS, but video embedding and deployment require it.

To enable IPFS:
1. Install IPFS Desktop or IPFS daemon
2. Start the daemon
3. Restart Andromica

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
