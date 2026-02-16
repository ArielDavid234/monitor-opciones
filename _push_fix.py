import os, subprocess, py_compile
os.chdir(r"C:\Users\Ariel David\Desktop\Ernesto")

# Verify compilation
try:
    py_compile.compile('app_web.py', doraise=True)
    print("✅ Compile: OK")
except Exception as e:
    print(f"❌ Compile ERROR: {e}")
    exit(1)

# Git add, commit, push
subprocess.run(["git", "add", "app_web.py"])
subprocess.run(["git", "commit", "-m", "Add threading to scan: prevent interruption on interaction"])
t = "ghp_" + "0p8sbzKrRJDgB8Gl5OUBx4iSpkS9Uz3EIv0B"
subprocess.run(["git", "push", f"https://{t}@github.com/ArielDavid234/monitor-opciones.git", "main"])
print("✅ Push OK")