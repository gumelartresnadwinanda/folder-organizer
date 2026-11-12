# Organizer - Folders & Files

A fast, compact local web application to organize folders or loose files by username directly inside your chosen directory. Built with Python, Flask, and Tailwind CSS following anti-slop UI principles.

## Features
- **Dual Mode Support:**
  - **Folders Mode:** Scans a parent directory to sort immediate child folders into username folders (skips nested folders automatically).
  - **Files Mode:** Scans a single directory containing loose files and moves them into username folders based on filename tokens or manual input.
- **Standalone Executable:** Run directly with `FolderOrganizer.exe` (no Python installation required).
- **Uncropped Media Previews:**
  - **Images:** Dedicated canvas with `object-contain` so 100% of images are visible without cropping.
  - **Videos:** Embedded HTML5 video player with seek and playback controls for `.mp4`, `.webm`, `.mov`, etc.
- **Smart Username Token Extraction:** Extracts usernames from brackets (`[userA]`, `(userB)`) as well as delimiters (`!!`, `_`, `-`, dots, spaces).
- **Selective Moving:** Choose exactly which files/folders to move with individual checkboxes before confirming.
- **Mobile-Friendly Layout:** Responsive stack on phones with sticky thumb-friendly action buttons and notch/safe-area support.
- **Undo Support:** Quickly revert recent moves with one click.
- **In-Page Directory Explorer:** Browse drives (`C:`, `D:`, `E:`) and navigate subfolders directly inside the browser.

## Running the Application
### Option 1: Standalone Executable (Windows)
Double-click `FolderOrganizer.exe`. It will launch the local service and open your default browser automatically.

### Option 2: Run with Python
```bash
pip install -r requirements.txt
python app.py
```
Open [http://localhost:5000](http://localhost:5000) in your browser.
