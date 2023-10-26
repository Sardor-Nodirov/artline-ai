import streamlit as st
import pyaudio
import asyncio
import aiohttp
import websockets
import sys
import pyaudio
import argparse
import asyncio
import aiohttp
import json
import os
import sys
import wave
import websockets
import requests
import tts

from datetime import datetime

startTime = datetime.now()

all_mic_data = []
all_transcripts = []
is_tts_speaking = False

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 8000

audio_queue = asyncio.Queue()

# Mimic sending a real-time stream by sending this many seconds of audio at a time.
# Used for file "streaming" only.
REALTIME_RESOLUTION = 0.250


# Used for microphone streaming only.
def mic_callback(input_data, frame_count, time_info, status_flag):
    audio_queue.put_nowait(input_data)
    return (input_data, pyaudio.paContinue)


async def run(key, method, format, **kwargs):
    deepgram_url = f'{kwargs["host"]}/v1/listen?punctuate=true&endpointing=0'

    if kwargs["model"]:
        deepgram_url += f"&model={kwargs['model']}"

    if kwargs["tier"]:
        deepgram_url += f"&tier={kwargs['tier']}"

    if method == "mic":
        deepgram_url += "&encoding=linear16&sample_rate=16000"

    elif method == "wav":
        data = kwargs["data"]
        deepgram_url += f'&channels={kwargs["channels"]}&sample_rate={kwargs["sample_rate"]}&encoding=linear16'

    # Connect to the real-time streaming endpoint, attaching our credentials.
    async with websockets.connect(
        deepgram_url, extra_headers={"Authorization": "Token {}".format(key)}
    ) as ws:
        print(f'ℹ️  Request ID: {ws.response_headers.get("dg-request-id")}')
        if kwargs["model"]:
            print(f'ℹ️  Model: {kwargs["model"]}')
        if kwargs["tier"]:
            print(f'ℹ️  Tier: {kwargs["tier"]}')
        print("🟢 (1/5) Successfully opened Deepgram streaming connection")

        async def sender(ws):
            print(
                f'🟢 (2/5) Ready to stream {method if (method == "mic" or method == "url") else kwargs["filepath"]} audio to Deepgram{". Speak into your microphone to transcribe." if method == "mic" else ""}'
            )

            if method == "mic":
                try:
                    while True:
                        mic_data = await audio_queue.get()
                        all_mic_data.append(mic_data)
                        await ws.send(mic_data)
                        
                except websockets.exceptions.ConnectionClosedOK:
                    await ws.send(json.dumps({"type": "CloseStream"}))
                    print(
                        "🟢 (5/5) Successfully closed Deepgram connection, waiting for final transcripts if necessary"
                    )

                except Exception as e:
                    print(f"Error while sending: {str(e)}")
                    raise

            elif method == "url":
                # Listen for the connection to open and send streaming audio from the URL to Deepgram
                async with aiohttp.ClientSession() as session:
                    async with session.get(kwargs["url"]) as audio:
                        while True:
                            remote_url_data = await audio.content.readany()
                            await ws.send(remote_url_data)

                            # If no data is being sent from the live stream, then break out of the loop.
                            if not remote_url_data:
                                break

            elif method == "wav":
                nonlocal data
                # How many bytes are contained in one second of audio?
                byte_rate = (
                    kwargs["sample_width"] * kwargs["sample_rate"] * kwargs["channels"]
                )
                # How many bytes are in `REALTIME_RESOLUTION` seconds of audio?
                chunk_size = int(byte_rate * REALTIME_RESOLUTION)

                try:
                    while len(data):
                        chunk, data = data[:chunk_size], data[chunk_size:]
                        # Mimic real-time by waiting `REALTIME_RESOLUTION` seconds
                        # before the next packet.
                        await asyncio.sleep(REALTIME_RESOLUTION)
                        # Send the data
                        await ws.send(chunk)

                    await ws.send(json.dumps({"type": "CloseStream"}))
                    print(
                        "🟢 (5/5) Successfully closed Deepgram connection, waiting for final transcripts if necessary"
                    )
                except Exception as e:
                    print(f"🔴 ERROR: Something happened while sending, {e}")
                    raise e

            return

        async def receiver(ws):
            """Print out the messages received from the server."""
            first_message = True
            first_transcript = True
            transcript = ""

            async for msg in ws:
                res = json.loads(msg)
                if first_message:
                    print(
                        "🟢 (3/5) Successfully receiving Deepgram messages, waiting for finalized transcription..."
                    )
                    first_message = False
                try:
                    # handle local server messages
                    if res.get("msg"):
                        print(res["msg"])
                    if res.get("is_final"):
                        transcript = (                          ###### user message
                            res.get("channel", {})
                            .get("alternatives", [{}])[0]
                            .get("transcript", "")
                        )
                        if transcript.strip() != "":
                            all_transcripts.append(transcript)

                        # if using the microphone, close stream if user says "goodbye"
                        if method == "mic" and "goodbye" in transcript.lower():
                            await ws.send(json.dumps({"type": "CloseStream"}))
                            print(
                                "🟢 (5/5) Successfully closed Deepgram connection, waiting for final transcripts if necessary"
                            )

                    if res.get("speech_final"):
                        if (res.get("channel", {})
                            .get("alternatives", [{}])[0]
                            .get("transcript", "")).strip() != "":
                            print("".join(all_transcripts))
                            #st.text("".join(all_transcripts))
                            response = send_transcript_to_get_response("".join(all_transcripts))
                            print(response['response'])
                            st.text(response['response'])
                            await ws.send(json.dumps({'type': 'KeepAlive'}))
                            tts.speak(response['response'])
                            await ws.send(json.dumps({'type': 'KeepAlive'}))
                            await ws.send(json.dumps({'type': 'KeepAlive'}))
                            all_transcripts.clear()

                    # handle end of stream
                    if res.get("created"):
                
                        print(
                            f'🟢 Request finished with a duration of {res["duration"]} seconds. Exiting!'
                        )
                except KeyError:
                    print(f"🔴 ERROR: Received unexpected API response! {msg}")

        # Set up microphone if streaming from mic
        async def microphone():
            audio = pyaudio.PyAudio()
            stream = audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK,
                stream_callback=mic_callback,
            )

            stream.start_stream()

            global SAMPLE_SIZE
            SAMPLE_SIZE = audio.get_sample_size(FORMAT)

            while stream.is_active():
                await asyncio.sleep(0.1)

            stream.stop_stream()
            stream.close()

        functions = [
            asyncio.ensure_future(sender(ws)),
            asyncio.ensure_future(receiver(ws)),
        ]

        if method == "mic":
            functions.append(asyncio.ensure_future(microphone()))

        await asyncio.gather(*functions)


def validate_input(input):
    if input.lower().startswith("mic"):
        return input

    elif input.lower().endswith("wav"):
        if os.path.exists(input):
            return input

    elif input.lower().startswith("http"):
        return input

    raise argparse.ArgumentTypeError(
        f'{input} is an invalid input. Please enter the path to a WAV file, a valid stream URL, or "mic" to stream from your microphone.'
    )

def send_transcript_to_get_response(transcript):
    # Define the endpoint URL (modify this as per your setup)
    endpoint_url = "http://localhost:5000/get_response"
    
    # Define the payload
    payload = {"message": transcript}

    # Make the POST request
    response = requests.post(endpoint_url, json=payload)


    # Return the response content
    return response.json()

def validate_format(format):
    if (
        format.lower() == ("text")
        or format.lower() == ("vtt")
        or format.lower() == ("srt")
    ):
        return format

    raise argparse.ArgumentTypeError(
        f'{format} is invalid. Please enter "text", "vtt", or "srt".'
    )

def validate_dg_host(dg_host):
    if (
        # Check that the host is a websocket URL
        dg_host.startswith("wss://")
        or dg_host.startswith("ws://")
    ):
        # Trim trailing slash if necessary
        if dg_host[-1] == '/':
            return dg_host[:-1]
        return dg_host 

    raise argparse.ArgumentTypeError(
            f'{dg_host} is invalid. Please provide a WebSocket URL in the format "{{wss|ws}}://hostname[:port]".'
    )

def parse_args():
    """Returns hardcoded arguments."""
    class Args:
        def __init__(self):
            self.key = ""
            self.input = "mic"
            self.model = "nova-2-ea"
            self.tier = ""
            self.timestamps = False
            self.format = "text"
            self.host = "wss://api.deepgram.com"
    
    return Args()

def streamlit_app():
    st.title("ArtLine - Art Museum AI")

    # Parse the command-line arguments.
    args = parse_args()
    input = args.input
    format = args.format.lower()
    host = args.host
    
    start_button = st.button("Start Conversation")
    
    if start_button:
        try:
            asyncio.run(run(args.key, "mic", format, model=args.model, tier=args.tier, host=host, timestamps=args.timestamps)) # Add necessary arguments here
        except Exception as e:
            st.error(f"Error: {e}")

if __name__ == "__main__":
    streamlit_app()
