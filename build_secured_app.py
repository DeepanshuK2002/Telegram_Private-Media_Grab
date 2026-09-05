import os
import sys
import subprocess
import shutil

def build(onefile=True):
    root_dir = os.path.dirname(os.path.abspath(__file__))
    entry_point = os.path.join(root_dir, "src", "gui.py")
    assets_dir = os.path.join(root_dir, "src", "assets")
    icon_path = os.path.join(assets_dir, "logo.ico")
    output_dir = os.path.join(root_dir, "dist")

    if not os.path.exists(entry_point):
        print(f"Error: Entry point not found at {entry_point}")
        sys.exit(1)

    cmd = [
        sys.executable, "-m", "nuitka",
        "--enable-plugin=pyside6",
        "--windows-console-mode=disable",
        f"--windows-icon-from-ico={icon_path}",
        f"--include-data-dir={assets_dir}=assets",
        "--include-package=ui",
        "--include-package=workers",
        "--include-package=utils",
        "--include-module=database",
        "--include-module=resource_utils",
        # Anti-reverse engineering & hardening flags:
        "--python-flag=no_docstrings",      # Strip all docstrings from functions/classes
        "--python-flag=no_asserts",         # Strip debug assertions
        "--lto=yes",                        # Link-Time Optimization for monolithic machine code
        "--assume-yes-for-downloads",       # Automatically accept required build tools
        "--remove-output",                  # Clean up intermediate C build files
        f"--output-dir={output_dir}",
        "--output-filename=TG_Private_Grab.exe",
        # Windows metadata
        '--windows-company-name=TG Private Grab',
        '--windows-product-name=TG Private Grab',
        '--windows-file-version=2.9.0.0',
        '--windows-product-version=2.9.0.0',
        '--windows-file-description=TG Private Grab Media Downloader',
    ]

    if onefile:
        cmd.append("--onefile")
        print("Packaging mode: Single standalone executable (--onefile)")
    else:
        cmd.append("--standalone")
        print("Packaging mode: Standalone folder distribution (--standalone)")

    cmd.append(entry_point)

    print("\nStarting Nuitka Ahead-of-Time Native C Compilation...")
    print("Translating Python source to C and compiling with MSVC into machine code...\n")

    result = subprocess.run(cmd, cwd=root_dir)
    if result.returncode == 0:
        print("\n" + "=" * 60)
        print("Build SUCCESSFUL!")
        if onefile:
            target_exe = os.path.join(output_dir, "TG_Private_Grab.exe")
            print(f"Secured executable created at:\n  {target_exe}")
        else:
            dist_folder = os.path.join(output_dir, "gui.dist")
            print(f"Secured distribution created at:\n  {dist_folder}")
        print("Your Python source code has been compiled into native machine code.")
        print("Python bytecode (.pyc) has been completely eliminated.")
        print("=" * 60)
    else:
        print(f"\nBuild failed with exit code: {result.returncode}")
        sys.exit(result.returncode)

if __name__ == "__main__":
    is_onefile = "--standalone" not in sys.argv
    build(onefile=is_onefile)
