import os, subprocess
os.chdir(r'C:\Users\Ariel David\Desktop\Ernesto')
subprocess.run(['git', 'add', 'ui/components.py'])
r = subprocess.run(['git', 'commit', '-m', 'Fix: use rgba() instead of hex-alpha for Plotly Bar colors'], capture_output=True, text=True)
print(r.stdout or r.stderr)
r = subprocess.run(['git', 'push', 'origin', 'main'], capture_output=True, text=True)
print(r.stdout or r.stderr)
print("Done!")
