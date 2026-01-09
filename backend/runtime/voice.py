import speech_recognition as sr
import subprocess

def transcribe_audio(audio_blob: bytes):
    try:
        # Convert incoming webm to wav using ffmpeg
        process = subprocess.run(
            ['ffmpeg', '-i', 'pipe:0', '-f', 'wav', 'pipe:1'],
            input=audio_blob,
            capture_output=True,
            binary=True,
            timeout=10
        )
        wav_data = process.stdout

        # We need to save to a temp file because SpeechRecognition 
        # library often prefers a file-like object or file path
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            tmp_file.write(wav_data)
            tmp_path = tmp_file.name
        
        r = sr.Recognizer()
        
        # Try to use Sphinx (Offline) first if available, else Google Online
        # NOTE: For this demo, we default to Google Online. 
        # For 100% offline, you must install pocketsphinx and configure it.
        try:
            with sr.AudioFile(tmp_path) as source:
                audio_data = r.record(source)
                text = r.recognize_google(audio_data)
        except sr.UnknownValueError:
            text = "" # Could not understand
        except sr.RequestError:
            text = "Error: API unavailable"

        os.unlink(tmp_path)
        return text
        
    except Exception as e:
        print(f"Voice Error: {e}")
        return None