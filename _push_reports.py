import subprocess
import sys

def run_git():
    try:
        # Add all changes
        print("Adding changes...")
        result = subprocess.run(
            ["git", "add", "."],
            capture_output=True,
            text=True,
            timeout=30
        )
        print(f"Add output: {result.stdout}")
        if result.stderr:
            print(f"Add stderr: {result.stderr}")
        
        # Commit
        print("\nCommitting...")
        commit_msg = "Reports: New .docx system - 4 buttons (Live/OI/Analysis/Range), removed CSV history"
        result = subprocess.run(
            ["git", "commit", "-m", commit_msg],
            capture_output=True,
            text=True,
            timeout=30
        )
        print(f"Commit output: {result.stdout}")
        if result.stderr:
            print(f"Commit stderr: {result.stderr}")
        
        # Push
        print("\nPushing to GitHub...")
        result = subprocess.run(
            ["git", "push", "origin", "main"],
            capture_output=True,
            text=True,
            timeout=60
        )
        print(f"Push output: {result.stdout}")
        if result.stderr:
            print(f"Push stderr: {result.stderr}")
        
        print("\n✅ Done!")
        
    except subprocess.TimeoutExpired:
        print("⏱️ Timeout - Git operation took too long")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    run_git()
