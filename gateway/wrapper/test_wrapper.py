# Description: A simple command-line script to test the gemini-wrapper.js service.
# This script starts the Node.js wrapper, allows sending multiple prompts from the CLI,
# and displays the responses, verifying that conversation context is maintained.

import subprocess
import sys
import threading
from pathlib import Path

# Get the path to the wrapper script, assuming it's in the same directory
WRAPPER_PATH = Path(__file__).parent / "gemini-wrapper.js"

def read_stderr(stream):
    """Continuously read from the stderr stream and print it with a prefix."""
    for line in iter(stream.readline, b''):
        print(f"[WRAPPER_STDERR] {line.decode('utf-8', 'replace').strip()}", flush=True)

def main():
    """Main function to run the interactive test chat."""
    if not WRAPPER_PATH.is_file():
        print(f"Error: Wrapper script not found at {WRAPPER_PATH.resolve()}")
        sys.exit(1)

    print(f"Starting Node.js wrapper: {WRAPPER_PATH.name}...")
    try:
        process = subprocess.Popen(
            ["node", str(WRAPPER_PATH)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError:
        print("Error: 'node' command not found. Please ensure Node.js is installed and in your PATH.")
        sys.exit(1)

    # Start a thread to monitor stderr so we can see debug messages from the wrapper
    stderr_thread = threading.Thread(target=read_stderr, args=(process.stderr,))
    stderr_thread.daemon = True
    stderr_thread.start()

    print("\nChat session started. Type 'exit' or 'quit' to end.")
    print("-" * 50)

    try:
        # First, wait for the wrapper to be ready by reading its initial debug output
        for _ in range(3): # Read up to 3 lines of initial output
            initial_output = process.stdout.readline().decode('utf-8', 'replace').strip()
            if "Waiting for prompts" in initial_output:
                break
        
        while True:
            try:
                user_input = input("You: ")
            except EOFError:
                print("\nExiting...")
                break

            if user_input.lower() in ["exit", "quit"]:
                print("\nExiting chat.")
                break
            
            if not user_input:
                continue

            # Send the user's prompt to the wrapper's stdin
            process.stdin.write((user_input + '\n').encode('utf-8'))
            process.stdin.flush()

            # Read the response from stdout until [END_RESPONSE] is found
            print("Gemini: ", end="", flush=True)
            while True:
                line_bytes = process.stdout.readline()
                if not line_bytes:
                    print("\n[ERROR] Wrapper process terminated unexpectedly.")
                    return # Exit main function

                line = line_bytes.decode('utf-8', 'replace').strip()

                if line == '[END_RESPONSE]':
                    print() # Newline after Gemini's full response
                    break
                
                # Filter out internal debug/status lines from the response
                if not line.startswith(("[DEBUG]", "[ERROR]")):
                    print(line, flush=True)
            
            print("-" * 50)

    finally:
        print("\nCleaning up and terminating wrapper process...")
        if process.poll() is None: # Check if process is still running
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        print("Cleanup complete.")

if __name__ == "__main__":
    main()
