import subprocess
import os
import json
import re

def run_ffmpeg_command(command: list, description: str):
    """Runs an FFmpeg command and prints its output."""
    print(f"\n--- {description} ---")
    try:
        process = subprocess.run(command, capture_output=True, text=True, check=True)
        print("STDOUT:\n", process.stdout)
        if process.stderr:
            print("STDERR (FFmpeg usually prints info here):\n", process.stderr)
        return process.stdout, process.stderr
    except subprocess.CalledProcessError as e:
        print(f"ERROR: FFmpeg command failed with exit code {e.returncode}")
        print("STDOUT:\n", e.stdout)
        print("STDERR:\n", e.stderr)
        raise
    except FileNotFoundError:
        print("ERROR: FFmpeg not found. Please ensure FFmpeg is installed and in your system's PATH.")
        raise

def get_audio_stats(audio_path: str):
    """Extracts audio statistics using FFmpeg's volumedetect filter."""
    command = [
        "ffmpeg",
        "-i", audio_path,
        "-filter_complex", "volumedetect",
        "-f", "null",
        "-"
    ]
    stdout, stderr = run_ffmpeg_command(command, f"Getting audio statistics for {audio_path}")
    
    stats = {}
    # Parse stderr for volumedetect output
    for line in stderr.splitlines():
        if "mean_volume" in line:
            match = re.search(r"mean_volume: ([-+]?\d*\.\d+|\d+) dB", line)
            if match:
                stats["mean_volume_db"] = float(match.group(1))
        elif "max_volume" in line:
            match = re.search(r"max_volume: ([-+]?\d*\.\d+|\d+) dB", line)
            if match:
                stats["max_volume_db"] = float(match.group(1))
        elif "histogram_0_db" in line: # This indicates clipping
            match = re.search(r"histogram_0_db: (\d+)", line)
            if match:
                stats["clipping_samples"] = int(match.group(1))
    return stats

def generate_spectrogram(audio_path: str, output_png_path: str):
    """Generates a spectrogram image for the given audio file."""
    command = [
        "ffmpeg",
        "-i", audio_path,
        "-lavfi", "showspectrumpic=s=1280x720:legend=1:color=magma",
        output_png_path
    ]
    run_ffmpeg_command(command, f"Generating spectrogram for {audio_path} to {output_png_path}")

def compare_audio_quality(original_audio_path: str, frontend_audio_path: str):
    """
    Compares the quality of two audio files by generating spectrograms and extracting statistics.
    """
    print(f"--- Comparing Audio Quality ---")
    print(f"Original Audio: {original_audio_path}")
    print(f"Frontend Audio: {frontend_audio_path}")

    if not os.path.exists(original_audio_path):
        print(f"ERROR: Original audio file not found at {original_audio_path}")
        return
    if not os.path.exists(frontend_audio_path):
        print(f"ERROR: Frontend audio file not found at {frontend_audio_path}")
        return

    # 1. Get Audio Statistics
    print("\n--- Audio Statistics ---")
    original_stats = get_audio_stats(original_audio_path)
    frontend_stats = get_audio_stats(frontend_audio_path)

    print("\nOriginal Audio Stats:")
    print(json.dumps(original_stats, indent=2))
    print("\nFrontend Audio Stats:")
    print(json.dumps(frontend_stats, indent=2))

    # 2. Generate Spectrograms
    output_dir = "audio_comparison_results"
    os.makedirs(output_dir, exist_ok=True)

    original_spectrogram_path = os.path.join(output_dir, f"original_spectrogram_{os.path.basename(original_audio_path)}.png")
    frontend_spectrogram_path = os.path.join(output_dir, f"frontend_spectrogram_{os.path.basename(frontend_audio_path)}.png")

    generate_spectrogram(original_audio_path, original_spectrogram_path)
    generate_spectrogram(frontend_audio_path, frontend_spectrogram_path)

    print(f"\nSpectrograms saved to:")
    print(f"- {original_spectrogram_path}")
    print(f"- {frontend_spectrogram_path}")
    print("\nVisually compare these images to identify differences in frequency content and noise.")
    print("\n--- Comparison Complete ---")

if __name__ == "__main__":
    # Example usage:
    # Replace these with your actual file paths
    # For testing, you might need to create dummy audio files or use existing ones.
    
    # Ensure 'audio.wav' exists from the frontend upload test
    frontend_audio = "audio_comparison_results/frontend_audio.wav" # Placeholder, you'd get this from your saved frontend upload
    original_audio = "original_high_quality.wav" # You need to provide this file

    # Create dummy files for demonstration if they don't exist
    if not os.path.exists(original_audio):
        print(f"WARNING: '{original_audio}' not found. Please provide an original audio file for comparison.")
        # You might want to create a dummy here for testing the script itself
        # For example, using pydub or scipy.io.wavfile as shown previously.
        # For now, we'll just exit if the original is missing.
        exit()
    
    # Assuming the frontend upload test saves the file as 'audio.wav' in the root directory
    # You might need to adjust this path based on where your API saves the uploaded file.
    # For example, if it saves to 'uploads/dataset_name/id_audio.wav'
    # You would need to know the dataset_name and id_audio from a successful upload.
    
    # For a more robust test, you'd integrate this with your API's saving mechanism
    # to get the path of the saved frontend audio.
    
    # For now, let's assume 'audio.wav' is the file saved by the frontend upload.
    # If your API saves it elsewhere, you'll need to adjust 'frontend_audio_path'
    # to point to the actual saved file.
    
    # Let's assume for this example that the frontend audio is saved as 'audio.wav'
    # in the current directory.
    frontend_audio_path_from_api = "data/uploads/common_voice/1.wav" # Example path from API save
    # You would need to replace '1.wav' with the actual id_audio and extension
    # and 'common_voice' with the actual dataset.

    # For a quick test, let's assume 'audio.wav' is the frontend audio
    # and 'original_high_quality.wav' is your reference.
    
    # IMPORTANT: You need to replace these paths with your actual files.
    # The 'frontend_audio_path' should point to the file saved by your API.
    # The 'original_audio_path' should point to your high-quality reference audio.
    
    # Example:
    # original_file = "path/to/your/original.wav"
    # frontend_file = "path/to/your/api_saved_audio.wav"
    
    # For demonstration, let's use placeholder paths.
    # The user will need to adjust these.
    
    # To run this script, you need to:
    # 1. Have FFmpeg installed and in your system's PATH.
    # 2. Provide an 'original_high_quality.wav' file.
    # 3. Provide the path to the audio file saved by your API (e.g., 'data/uploads/common_voice/1.wav').
    
    # Let's use the 'audio.wav' that the user mentioned for the frontend audio.
    # And a placeholder for the original.
    
    original_file_for_comparison = "original_high_quality.wav"
    frontend_file_for_comparison = "audio.wav" # This is the file the user mentioned

    if not os.path.exists(original_file_for_comparison):
        print(f"ERROR: Original audio file '{original_file_for_comparison}' not found.")
        print("Please create or specify the correct path to your high-quality reference audio.")
        exit(1)
    
    if not os.path.exists(frontend_file_for_comparison):
        print(f"ERROR: Frontend audio file '{frontend_file_for_comparison}' not found.")
        print("Please ensure your API has successfully saved an audio file named 'audio.wav' in the current directory, or specify the correct path.")
        exit(1)

    compare_audio_quality(original_file_for_comparison, frontend_file_for_comparison)
