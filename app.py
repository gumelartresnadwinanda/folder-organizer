import os
import re
import sys
import shutil
import subprocess
import mimetypes
import threading
import webbrowser
from pathlib import Path
from flask import Flask, request, jsonify, render_template, send_file

# Resolve template and resource paths for PyInstaller standalone bundle
def get_resource_dir():
    if getattr(sys, 'frozen', False):
        return getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

resource_dir = get_resource_dir()
template_dir = os.path.join(resource_dir, 'templates')
static_dir = os.path.join(resource_dir, 'static')

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

# In-memory history for Undo functionality
move_history = []
known_usernames = set()

def sanitize_folder_name(name):
    """Remove illegal Windows characters and strip whitespace."""
    cleaned = re.sub(r'[<>:"/\\|?*]', '', name).strip()
    return cleaned

def extract_tokens(name):
    """
    Extract meaningful username / tag tokens from folder or file names.
    Supports:
      - [userA] [anything]
      - [userA][anything] (no spaces)
      - (userA)(anything)
      - {userA}{anything}
      - Delimiters: !!, _, -, space, dots
    """
    # Strip file extension if present
    base_name = os.path.splitext(name)[0]
    tokens = []
    
    # 1. Matches inside [...], (...), or {...}
    bracket_matches = re.findall(r'\[([^\]]+)\]|\(([^)]+)\)|\{([^}]+)\}', base_name)
    for match in bracket_matches:
        for group in match:
            clean_grp = group.strip()
            if clean_grp:
                tokens.append(clean_grp)
    
    # Deduplicate preserving order
    seen = set()
    result = []
    for t in tokens:
        if t and t.lower() not in seen:
            seen.add(t.lower())
            result.append(t)
            
    # Also split by delimiters (words separated by !!, _, -, space, etc.)
    parts = re.split(r'[!@#$%^&*()_+=\-\[\]{};:\'",.<>?/\\|\s]+', base_name)
    for p in parts:
        p = p.strip()
        # Keep tokens with length >= 2
        if p and len(p) >= 2 and p.lower() not in seen:
            seen.add(p.lower())
            result.append(p)
                
    return result

def is_image_file(filename):
    ext = os.path.splitext(filename)[1].lower()
    return ext in {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}

def is_video_file(filename):
    ext = os.path.splitext(filename)[1].lower()
    return ext in {'.mp4', '.webm', '.mov', '.mkv', '.avi'}

def analyze_folder(folder_path):
    """
    Inspects immediate children of a folder:
    - Checks if it contains any subfolders
    - Counts files
    - Finds sample files and image files for uncropped preview
    """
    has_subfolders = False
    file_count = 0
    subfolder_names = []
    sample_files = []
    image_files = []

    try:
        with os.scandir(folder_path) as it:
            for entry in it:
                if entry.is_dir(follow_symlinks=False):
                    has_subfolders = True
                    subfolder_names.append(entry.name)
                elif entry.is_file(follow_symlinks=False):
                    file_count += 1
                    if len(sample_files) < 8:
                        sample_files.append(entry.name)
                    if is_image_file(entry.name):
                        image_files.append(entry.name)
    except (PermissionError, FileNotFoundError):
        pass

    # Sort images naturally
    image_files.sort()

    return {
        'has_subfolders': has_subfolders,
        'subfolder_count': len(subfolder_names),
        'subfolders': subfolder_names[:5],
        'file_count': file_count,
        'sample_files': sample_files,
        'image_files': image_files[:16],
        'preview_file': image_files[0] if image_files else None
    }

def pick_folder_dialog(initial_dir=""):
    """
    Opens the Windows native folder picker.
    In Python mode: runs Tkinter in a standalone subprocess.
    In Frozen .exe mode: uses PowerShell FolderBrowserDialog.
    """
    is_frozen = getattr(sys, 'frozen', False)

    if not is_frozen:
        script = f'''
import sys
import os
try:
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.lift()
    root.wm_attributes("-topmost", 1)
    root.focus_force()
    init_dir = r"""{initial_dir}"""
    initial = init_dir if init_dir and os.path.isdir(init_dir) else None
    selected = filedialog.askdirectory(initialdir=initial, title="Select Directory with Folders to Organize")
    root.destroy()
    if selected:
        print(selected.strip())
except Exception as e:
    sys.exit(1)
'''
        try:
            proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=180)
            if proc.returncode == 0 and proc.stdout.strip():
                return proc.stdout.strip()
        except Exception as e:
            print(f"[Dialog Tkinter Warning]: {e}")

    # Standalone PowerShell FolderBrowserDialog fallback
    try:
        ps_cmd = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$f = New-Object System.Windows.Forms.FolderBrowserDialog; "
            "$f.Description = 'Select Directory with Folders to Organize'; "
            "$f.ShowNewFolderButton = $true; "
            "if ($f.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output $f.SelectedPath }"
        )
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=180)
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    except Exception as e:
        print(f"[Dialog PowerShell Warning]: {e}")

    return None

@app.route('/api/list_dirs', methods=['GET', 'POST'])
def list_dirs():
    """Returns available drives or subdirectories for the web-based folder browser."""
    data = request.get_json(silent=True) or {}
    path = data.get('path', request.args.get('path', '')).strip()

    if not path:
        # Return Windows drive letters (C:\, D:\, E:\, etc.)
        import string
        import ctypes
        drives = []
        try:
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            for letter in string.ascii_uppercase:
                if bitmask & 1:
                    d = f"{letter}:\\"
                    if os.path.exists(d):
                        drives.append(d)
                bitmask >>= 1
        except Exception:
            drives = ['C:\\', 'D:\\', 'E:\\']
        return jsonify({'type': 'drives', 'items': drives, 'current': ''})

    norm_path = os.path.normpath(path)
    if not os.path.isdir(norm_path):
        return jsonify({'error': 'Not a valid directory.'}), 400

    parent = os.path.dirname(norm_path)
    if parent == norm_path:
        parent = ''  # At drive root, going up goes back to drive list

    subdirs = []
    try:
        with os.scandir(norm_path) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        subdirs.append(entry.name)
                except PermissionError:
                    pass
        subdirs.sort(key=lambda s: s.lower())
    except (PermissionError, Exception) as e:
        return jsonify({'error': f'Permission denied: {e}'}), 403

    return jsonify({
        'type': 'directories',
        'current': norm_path,
        'parent': parent,
        'items': subdirs
    })

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/current_dir', methods=['GET'])
def get_current_directory():
    """Returns the working directory where the server is hosted."""
    return jsonify({'path': os.path.normpath(os.getcwd())})

@app.route('/api/browse', methods=['POST'])
def browse_directory():
    """Opens native Windows folder selection dialog in a dedicated subprocess."""
    try:
        data = request.get_json(silent=True) or {}
        initial_dir = data.get('initial_dir', '').strip() or os.getcwd()
        
        selected_path = pick_folder_dialog(initial_dir)
        
        if selected_path:
            normalized = os.path.normpath(selected_path)
            return jsonify({'path': normalized, 'success': True})
        return jsonify({'path': '', 'cancelled': True, 'success': False})
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@app.route('/api/scan', methods=['POST'])
def scan_directory():
    """
    Scans directory in either 'folders' or 'files' mode:
    - 'folders' mode: scans immediate subfolders, skips folders that have nested subfolders.
    - 'files' mode: scans immediate files, ignores subfolders, extracts tokens and media type.
    """
    data = request.get_json(silent=True) or {}
    dir_path = data.get('path', '').strip()
    mode = data.get('mode', 'folders')

    print(f"[*] Scan requested for path: {dir_path} (mode: {mode})")

    if not dir_path or not os.path.isdir(dir_path):
        return jsonify({'error': 'Directory does not exist or invalid path.'}), 400

    if mode == 'files':
        ready_items = []
        try:
            entries = sorted(os.scandir(dir_path), key=lambda e: e.name.lower())
            for entry in entries:
                if not entry.is_file(follow_symlinks=False):
                    continue

                if entry.name.startswith('.') or entry.name.lower() in {'desktop.ini', 'thumbs.db'}:
                    continue

                stat = entry.stat()
                size_kb = round(stat.st_size / 1024, 1)
                size_str = f"{size_kb} KB" if size_kb < 1024 else f"{round(size_kb / 1024, 1)} MB"

                is_img = is_image_file(entry.name)
                is_vid = is_video_file(entry.name)
                tokens = extract_tokens(entry.name)

                ready_items.append({
                    'name': entry.name,
                    'path': os.path.normpath(entry.path),
                    'size': stat.st_size,
                    'size_str': size_str,
                    'is_image': is_img,
                    'is_video': is_vid,
                    'ext': os.path.splitext(entry.name)[1].lower(),
                    'tokens': tokens,
                    'status': 'ready'
                })

            return jsonify({
                'success': True,
                'mode': 'files',
                'base_path': os.path.normpath(dir_path),
                'total_items': len(ready_items),
                'ready_items': ready_items,
                'skipped_items': [],
                'known_usernames': sorted(list(known_usernames))
            })
        except Exception as e:
            return jsonify({'error': str(e), 'success': False}), 500

    # Default: Folders mode
    ready_folders = []
    skipped_folders = []

    try:
        entries = sorted(os.scandir(dir_path), key=lambda e: e.name.lower())
        for entry in entries:
            if not entry.is_dir(follow_symlinks=False):
                continue

            analysis = analyze_folder(entry.path)
            tokens = extract_tokens(entry.name)

            folder_item = {
                'name': entry.name,
                'path': os.path.normpath(entry.path),
                'has_subfolders': analysis['has_subfolders'],
                'subfolder_count': analysis['subfolder_count'],
                'subfolders': analysis['subfolders'],
                'file_count': analysis['file_count'],
                'sample_files': analysis['sample_files'],
                'preview_file': analysis['preview_file'],
                'image_files': analysis.get('image_files', []),
                'tokens': tokens
            }

            if analysis['has_subfolders']:
                folder_item['status'] = 'skipped'
                folder_item['reason'] = f"Contains {analysis['subfolder_count']} subfolder(s)"
                skipped_folders.append(folder_item)
            else:
                folder_item['status'] = 'ready'
                ready_folders.append(folder_item)

        return jsonify({
            'success': True,
            'mode': 'folders',
            'base_path': os.path.normpath(dir_path),
            'total_items': len(ready_folders) + len(skipped_folders),
            'ready_items': ready_folders,
            'skipped_items': skipped_folders,
            'known_usernames': sorted(list(known_usernames))
        })
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@app.route('/api/preview', methods=['GET'])
def get_file_preview():
    """Serves image or video files with Range support."""
    folder_path = request.args.get('folder', '')
    filename = request.args.get('file', '')

    if not folder_path or not filename:
        return 'Missing parameters', 400

    full_path = os.path.normpath(os.path.join(folder_path, filename))
    if not os.path.isfile(full_path):
        return 'File not found', 404

    mime, _ = mimetypes.guess_type(full_path)
    return send_file(full_path, mimetype=mime or 'application/octet-stream', conditional=True)

@app.route('/api/move', methods=['POST'])
def move_items():
    """
    Moves specified folders or files into a subfolder named after the selected username
    inside the SAME base directory.
    """
    data = request.get_json(silent=True) or {}
    base_path = data.get('base_path', '').strip()
    username = sanitize_folder_name(data.get('username', ''))
    item_names = data.get('items') or data.get('folder_names', [])
    mode = data.get('mode', 'folders')

    if not base_path or not os.path.isdir(base_path):
        return jsonify({'error': 'Invalid base path.'}), 400

    if not username:
        return jsonify({'error': 'Username cannot be blank or contain only invalid characters.'}), 400

    if not item_names or not isinstance(item_names, list):
        return jsonify({'error': 'No items selected to move.'}), 400

    dest_dir = os.path.normpath(os.path.join(base_path, username))
    
    # Destination directory creation inside same parent directory
    try:
        os.makedirs(dest_dir, exist_ok=True)
    except Exception as e:
        return jsonify({'error': f'Failed to create destination directory: {e}'}), 500

    moved_records = []
    errors = []

    for iname in item_names:
        src_path = os.path.normpath(os.path.join(base_path, iname))

        # Security & sanity checks
        if not os.path.exists(src_path):
            errors.append(f'Source not found: {iname}')
            continue

        if mode == 'folders' and not os.path.isdir(src_path):
            errors.append(f'Not a directory: {iname}')
            continue

        if mode == 'files' and not os.path.isfile(src_path):
            errors.append(f'Not a file: {iname}')
            continue

        if os.path.exists(dest_dir) and os.path.samefile(src_path, dest_dir):
            errors.append(f'Cannot move destination into itself: {iname}')
            continue

        # Target path inside username folder
        target_path = os.path.normpath(os.path.join(dest_dir, iname))

        # Handle naming conflict
        counter = 1
        if mode == 'files':
            stem, ext = os.path.splitext(iname)
            while os.path.exists(target_path):
                target_path = os.path.normpath(os.path.join(dest_dir, f"{stem}_{counter}{ext}"))
                counter += 1
        else:
            while os.path.exists(target_path):
                target_path = os.path.normpath(os.path.join(dest_dir, f"{iname}_{counter}"))
                counter += 1

        try:
            shutil.move(src_path, target_path)
            moved_records.append({
                'source': src_path,
                'destination': target_path,
                'item_name': iname
            })
        except Exception as e:
            errors.append(f'Error moving {iname}: {str(e)}')

    if moved_records:
        known_usernames.add(username)
        move_history.append({
            'username': username,
            'base_path': base_path,
            'dest_dir': dest_dir,
            'mode': mode,
            'records': moved_records
        })

    return jsonify({
        'success': True,
        'mode': mode,
        'username': username,
        'moved_count': len(moved_records),
        'moved_items': [r['item_name'] for r in moved_records],
        'destination': dest_dir,
        'errors': errors,
        'known_usernames': sorted(list(known_usernames))
    })

@app.route('/api/undo', methods=['POST'])
def undo_last_move():
    """Reverts the last move batch (works for both files and folders)."""
    if not move_history:
        return jsonify({'error': 'No moves to undo.'}), 400

    last_batch = move_history.pop()
    reverted = []
    errors = []

    for record in reversed(last_batch['records']):
        dest = record['destination']
        src = record['source']
        item_label = record.get('item_name') or record.get('folder_name', '')
        try:
            if os.path.exists(dest):
                shutil.move(dest, src)
                reverted.append(item_label)
        except Exception as e:
            errors.append(f"Failed to restore {item_label}: {str(e)}")

    # Clean up empty username directory if it is empty
    try:
        if os.path.exists(last_batch['dest_dir']) and not os.listdir(last_batch['dest_dir']):
            os.rmdir(last_batch['dest_dir'])
    except Exception:
        pass

    return jsonify({
        'success': True,
        'reverted_count': len(reverted),
        'reverted_items': reverted,
        'errors': errors
    })

def open_browser():
    import time
    time.sleep(1.2)
    try:
        webbrowser.open('http://localhost:5000')
    except Exception:
        pass

if __name__ == '__main__':
    port = 5000
    print(f"[*] Starting Folder Organizer on http://localhost:{port}")
    print("[*] Open your browser at http://localhost:5000")
    if not os.environ.get('WERKZEUG_RUN_MAIN'):
        threading.Thread(target=open_browser, daemon=True).start()
    app.run(host='127.0.0.1', port=port, debug=False)
