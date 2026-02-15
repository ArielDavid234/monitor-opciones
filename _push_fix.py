import os, subprocess
os.chdir(r"C:\Users\Ariel David\Desktop\Ernesto")
subprocess.run(["git", "add", "core/scanner.py"])
subprocess.run(["git", "commit", "-m", "FIX: Optimized anti-ban system"])
subprocess.run(["git", "push"])
print("OK")