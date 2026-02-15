import subprocess, os

# Push fix
subprocess.run(["git", "add", "."], timeout=10)
r = subprocess.run(["git", "commit", "-m", "Fix: remove leftover old Reports code causing IndentationError"], capture_output=True, text=True, timeout=15)
print(r.stdout.strip())
r2 = subprocess.run(["git", "push", "origin", "main"], capture_output=True, text=True, timeout=30)
print(r2.stdout.strip() if r2.stdout.strip() else r2.stderr.strip())

# Self-cleanup
os.remove("_push_reports.py")
subprocess.run(["git", "add", "."], timeout=10)
r3 = subprocess.run(["git", "commit", "-m", "Remove temp script"], capture_output=True, text=True, timeout=10)
print(r3.stdout.strip())
r4 = subprocess.run(["git", "push", "origin", "main"], capture_output=True, text=True, timeout=30)
print(r4.stdout.strip() if r4.stdout.strip() else r4.stderr.strip())
print("Done")
