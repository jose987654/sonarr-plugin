# 🚀 Quick Setup Steps - Sonarr-Seedr Plugin

**Follow these simple steps to get your plugin running on Windows.**

## 🔄 How It Works

This plugin acts as a bridge between Sonarr and Seedr cloud storage. Here's how the folder system works:

- **Torrent Folder**: Sonarr stores `.torrent` files here → Plugin watches this folder → Uploads to Seedr cloud
- **Watch Folder**: Plugin downloads completed files here → Sonarr imports from this folder → Organizes your TV shows

**The key**: Both Sonarr and the plugin must use the EXACT SAME folder paths for everything to work automatically. When you drop a torrent file into the Torrent Folder, the entire process happens automatically: Sonarr → Plugin → Seedr → Plugin → Sonarr → Organized TV show!

---

## 📋 Prerequisites (5 minutes)

1. **Create Seedr account**: [https://www.seedr.cc](https://www.seedr.cc)
2. **Install Sonarr** (optional): [https://sonarr.tv](https://sonarr.tv)
3. **Download plugin**: Get `SonarrSeedr-SIMPLE.zip` from releases

---

## ⚡ Installation (2 minutes)

1. **Extract** `SonarrSeedr-SIMPLE.zip` to `C:\SonarrSeedr\`
2. **Run** `SonarrSeedr.exe`
3. **Wait** for browser to open `http://localhost:8000`

---

## ⚙️ Configuration (5 minutes)

### Step 1: Connect to Seedr

1. **Click** "Start Authentication" in the plugin web interface
2. **Copy** the device code (e.g., `AB12-CD34`)
3. **Go to** [https://www.seedr.cc/device](https://www.seedr.cc/device)
4. **Enter** the code and approve
5. **Wait** for "Connected to Seedr" status

### Step 2: Configure Plugin Folders

1. **In the plugin web interface**, go to Settings/Configuration
2. **Set the SAME folders** you will use in Sonarr:
   - **Torrent Folder**: Same folder you'll set in Sonarr (e.g., `D:\Torrents\`)
   - **Watch Folder**: Same folder you'll set in Sonarr (e.g., `D:\Downloads\`)
3. **Click** "Save Configuration"

### Step 3: Add Plugin as Download Client in Sonarr

1. **Open Sonarr** web interface (`http://localhost:8989`)
2. **Click** "Settings" (gear icon) in the top menu
3. **Click** "Download Clients" in the left sidebar
4. **Click** the "+" button (Add Download Client)
5. **Select** "Torrent Blackhole" from the dropdown list
6. **Fill in the form**:
   - **Name**: Type "Sonarr-Seedr Plugin"
   - **Enable**: ✓ Check this box
   - **Torrent Folder**: Click folder icon, choose the SAME folder you set in the plugin (e.g., `D:\Torrents\`)
   - **Watch Folder**: Click folder icon, choose the SAME folder you set in the plugin (e.g., `D:\Downloads\`)
   - **Save Magnet Files**: ✓ Check this box
   - **Save Magnet Files Extension**: Keep as `.magnet`
7. **Click** "Test" button (should show green checkmark)
8. **Click** "Save" button
9. **Make sure the download client is ENABLED** in Sonarr (check the Enable checkbox)
10. **Test the setup**: Drop a .torrent file in your Torrent Folder to verify everything works

---

## 🎯 How to Use

### Daily Process

1. **Find a TV show torrent** (from EZTV, RARBG, etc.)
2. **Download the .torrent file** to your computer
3. **Drop the .torrent file** into your **Torrent Folder** (the one you set in Sonarr)
4. **Everything happens automatically**:
   - Sonarr detects the torrent
   - Plugin uploads to Seedr cloud
   - Plugin downloads to your computer
   - Sonarr organizes the show

### What to Check

- **Sonarr**: `http://localhost:8989` - See your organized TV shows
- **Seedr**: [https://www.seedr.cc](https://www.seedr.cc) - See cloud downloads
- **Plugin**: `http://localhost:8000` - Monitor progress

### Important

- **Keep the plugin running** - It needs to be open to work
- **Use the same folders** - Torrent Folder and Watch Folder you set in Sonarr

---

## 🔧 Quick Troubleshooting

| Problem                 | Solution                                    |
| ----------------------- | ------------------------------------------- |
| App won't start         | Run as Administrator or use `debug.bat`     |
| Port 8000 busy          | Run `SonarrSeedr.exe --port 8001`           |
| Authentication fails    | Check internet, try new device code         |
| Torrents not processing | Check file extensions (.torrent or .magnet) |
| Sonarr not connecting   | Verify API key and Sonarr is running        |

---

## ✅ Success Checklist

- [ ] Plugin web interface loads at `http://localhost:8000`
- [ ] Connected to Seedr account
- [ ] Sonarr download client configured
- [ ] Test: Drop a .torrent file in your Torrent Folder

---

**That's it! You're ready to automatically download and organize TV shows.** 🎬

_For detailed help, see `WINDOWS_SETUP_GUIDE.md`_
