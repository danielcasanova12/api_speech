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
   
    
    original_file_for_comparison = "Gravação (5).m4a"
    frontend_file_for_comparison = "100008.webm" # This is the file the user mentioned

    if not os.path.exists(original_file_for_comparison):
        print(f"ERROR: Original audio file '{original_file_for_comparison}' not found.")
        print("Please create or specify the correct path to your high-quality reference audio.")
        exit(1)
    
    if not os.path.exists(frontend_file_for_comparison):
        print(f"ERROR: Frontend audio file '{frontend_file_for_comparison}' not found.")
        print("Please ensure your API has successfully saved an audio file named 'audio.wav' in the current directory, or specify the correct path.")
        exit(1)

    compare_audio_quality(original_file_for_comparison, frontend_file_for_comparison)
