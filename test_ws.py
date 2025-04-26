#!/usr/bin/env python3
import asyncio
import logging
from obsws_python import obsws, requests

# Configure logging to see debug output
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')

async def test_obs_recording():
    host = "localhost"
    port = 4455
    password = ""  # No password setup in OBS WebSocket

    # Initialize the OBS WebSocket client
    ws = obsws(host=host, port=port, password=password)
    try:
        logging.info("Connecting to OBS WebSocket...")
        await ws.connect()
        logging.info("Connected successfully.")
        
        # Get and print current recording status
        status = await ws.call(requests.GetRecordingStatus())
        logging.info(f"Recording active: {status.get_recording()}")

        # Start recording
        logging.info("Starting recording for 5 seconds...")
        await ws.call(requests.StartRecording())
        await asyncio.sleep(5)

        # Stop recording
        logging.info("Stopping recording...")
        await ws.call(requests.StopRecording())

    except Exception as e:
        logging.error(f"Error during OBS WebSocket test: {e}")
    finally:
        # Always disconnect cleanly
        await ws.disconnect()
        logging.info("Disconnected from OBS WebSocket.")

if __name__ == "__main__":
    asyncio.run(test_obs_recording())
