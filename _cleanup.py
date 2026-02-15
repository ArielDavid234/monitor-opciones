import subprocess
import os

# Eliminar scripts temporales
scripts = ["_push_reports.py", "_check_git.py"]

for script in scripts:
    try:
        if os.path.exists(script):
            os.remove(script)
            print(f"✓ Deleted {script}")
    except Exception as e:
        print(f"✗ Error deleting {script}: {e}")

# Commit la limpieza
try:
    subprocess.run(["git", "add", "."], timeout=10)
    result = subprocess.run(
        ["git", "commit", "-m", "Clean up temp scripts"],
        capture_output=True, text=True, timeout=10
    )
    if "nothing to commit" not in result.stdout:
        subprocess.run(["git", "push", "origin", "main"], timeout=30)
        print("\n✓ Cleanup committed and pushed")
    else:
        print("\n✓ Nothing to clean up")
except Exception as e:
    print(f"\n✗ Error: {e}")
