"""
Build Deadboy4D into a distributable Windows package.

Usage:
    pip install pyinstaller
    python build.py

Output: dist/Deadboy4D/ folder with .exe and all needed files
"""

import subprocess
import shutil
import os

def build():
    print("=" * 50)
    print("  Building Deadboy4D Analytics")
    print("=" * 50)

    # Clean previous builds
    for d in ["build", "dist"]:
        if os.path.exists(d):
            shutil.rmtree(d)

    # PyInstaller command
    cmd = [
        "pyinstaller",
        "--name=Deadboy4D",
        "--noconfirm",
        "--console",          # show console for server logs
        "--icon=NONE",
        # Add data files
        "--add-data=dashboard.html;.",
        "--add-data=scraper_sportstoto.py;.",
        "--add-data=scraper_magnum.py;.",
        "--add-data=scraper_damacai.py;.",
        "--add-data=fix_magnum.py;.",
        # Hidden imports that PyInstaller might miss
        "--hidden-import=numpy",
        "--hidden-import=pandas",
        "--hidden-import=flask",
        "--hidden-import=bs4",
        "--hidden-import=requests",
        "--hidden-import=scipy",
        # Entry point
        "server.py",
    ]

    print("\nRunning PyInstaller...")
    result = subprocess.run(cmd, capture_output=False)

    if result.returncode != 0:
        print("\n[ERROR] PyInstaller failed!")
        return

    # Copy data folder if it exists
    dist_dir = os.path.join("dist", "Deadboy4D")
    data_dir = os.path.join(dist_dir, "data")
    if os.path.exists("data"):
        print("\nCopying data folder...")
        shutil.copytree("data", data_dir)
    else:
        os.makedirs(data_dir, exist_ok=True)

    # Copy README
    if os.path.exists("README.md"):
        shutil.copy("README.md", dist_dir)

    # Create a launcher batch file for convenience
    bat_path = os.path.join(dist_dir, "START.bat")
    with open(bat_path, "w") as f:
        f.write('@echo off\n')
        f.write('echo Starting Deadboy4D Analytics...\n')
        f.write('echo Open your browser: http://localhost:8080\n')
        f.write('echo.\n')
        f.write('Deadboy4D.exe\n')
        f.write('pause\n')

    print(f"\n{'=' * 50}")
    print(f"  Build complete!")
    print(f"  Output: dist/Deadboy4D/")
    print(f"  Run:    dist/Deadboy4D/START.bat")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    build()
