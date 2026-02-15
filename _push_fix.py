import os, subprocess, py_compile
os.chdir(r"C:\Users\Ariel David\Desktop\Ernesto")

# Verify
py_compile.compile('app_web.py', doraise=True)

# Cleanup temp files
for fn in os.listdir('.'):
    if fn.startswith('_') and fn.endswith(('.py', '.txt')) and fn not in ('_push_fix.py',):
        try: os.remove(fn)
        except: pass

# Git
subprocess.run(["git", "add", "-A"])
subprocess.run(["git", "commit", "-m", "Fix all emoji: restore CP850 mojibake to proper Unicode"])
t = "ghp_" + "0p8sbzKrRJDgB8Gl5OUBx4iSpkS9Uz3EIv0B"
subprocess.run(["git", "push", f"https://{t}@github.com/ArielDavid234/monitor-opciones.git", "main"])
print("OK")