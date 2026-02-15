import os, subprocess
os.chdir(r'C:\Users\Ariel David\Desktop\Ernesto')

# Check if there are actual changes
r = subprocess.run(['git', 'diff', '--name-only', 'ui/components.py'], capture_output=True, text=True)
print(f"Diff: '{r.stdout.strip()}'")

if r.stdout.strip():
    subprocess.run(['git', 'add', 'ui/components.py'])
    r = subprocess.run(['git', 'commit', '-m', 'Fix: use rgba() instead of hex-alpha for Plotly Bar colors'], capture_output=True, text=True)
    print(r.stdout or r.stderr)
    r = subprocess.run(['git', 'push', 'origin', 'main'], capture_output=True, text=True)
    print(r.stdout or r.stderr)
else:
    # Force add all changes
    subprocess.run(['git', 'add', '-A'])
    r = subprocess.run(['git', 'status', '--short'], capture_output=True, text=True)
    print(f"Status: '{r.stdout.strip()}'")
    if r.stdout.strip():
        r = subprocess.run(['git', 'commit', '-m', 'Fix: use rgba() instead of hex-alpha for Plotly Bar colors'], capture_output=True, text=True)
        print(r.stdout or r.stderr)
        r = subprocess.run(['git', 'push', 'origin', 'main'], capture_output=True, text=True)
        print(r.stdout or r.stderr)
    else:
        print("No changes to commit!")
print("Done!")
