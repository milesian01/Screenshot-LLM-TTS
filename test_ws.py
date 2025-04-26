#!/usr/bin/env python3
import time
from obsws_python import ReqClient

def main():
    # adjust host/port/password if needed
    client = ReqClient(host="localhost", port=4455, password="", timeout=5)
    try:
        # 1) Check connection by fetching version
        version = client.get_version()
        print(f"Connected to OBS v{version.obs_version} (ws v{version.obs_web_socket_version})")

        # 2) Query current recording status
        status = client.get_record_status()
        print(f"Recording active? {status.output_active}")

        # 3) Start a 5-second recording
        print("→ Starting recording…")
        client.start_record()
        time.sleep(5)

        # 4) Stop recording
        print("→ Stopping recording…")
        client.stop_record()
        print("Done.")
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        client.disconnect()

if __name__ == "__main__":
    main()
