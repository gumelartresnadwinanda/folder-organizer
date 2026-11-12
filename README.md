# Folder Organizer by Username

A fast, compact local web application to organize folders by username directly inside your chosen directory. Built with Python, Flask, and Tailwind CSS following anti-slop UI principles.

## Features
- **Standalone Executable:** Run directly with `FolderOrganizer.exe` (no Python installation required).
- **Uncropped Image Previews:** Dedicated canvas with `object-contain` so 100% of images are visible without cropping or clipping. Multi-image switcher allows previewing all photos in a folder.
- **Auto-Skip Nested Folders:** Automatically scans folders and skips any folder that contains nested subfolders, preserving multi-tier directories.
- **Smart Username Token Extraction:** Extracts usernames with or without spaces (e.g. `[userA] [anything]`, `[userB][anything]`, `(...)`, or `{...}`) and provides one-click quick-fill badges.
- **Selective Moving:** You choose exactly which folders to move with individual checkboxes before confirming.
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
