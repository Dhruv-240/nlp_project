import subprocess
import os
import signal
import time
import sys

def install_requirements():
    """Installs packages from requirements.txt."""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("Successfully installed requirements.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to install requirements: {e}")
        sys.exit(1)

def find_and_kill_process_on_port(port):
    """Finds and kills the process running on the given port."""
    try:
        import psutil
    except ImportError:
        print("psutil is not installed. Please install it with 'pip install psutil'")
        sys.exit(1)

    for proc in psutil.process_iter(['pid', 'name']):
        try:
            for conn in proc.connections(kind='inet'):
                if conn.laddr.port == port:
                    print(f"Found process {proc.info['pid']} ({proc.info['name']}) on port {port}. Terminating...")
                    os.kill(proc.info['pid'], signal.SIGTERM)
                    proc.wait()
                    print(f"Process {proc.info['pid']} terminated.")
                    return
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    print(f"No process found on port {port}.")

if __name__ == "__main__":
    install_requirements()
    find_and_kill_process_on_port(8501)

    # Start the Streamlit app
    streamlit_process = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app.py"])
    print("Frontend and backend are starting...")

    # Wait for user to quit
    while True:
        try:
            user_input = input("Enter 'q' to quit: ")
            if user_input.lower() == 'q':
                break
        except (KeyboardInterrupt, EOFError):
            # Handle Ctrl+C or Ctrl+D as a quit signal
            break

    # Terminate the Streamlit process
    print("Quitting the application...")
    os.kill(streamlit_process.pid, signal.SIGTERM)
    streamlit_process.wait()
    print("Application has been shut down.")