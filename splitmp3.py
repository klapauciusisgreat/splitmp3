#!/usr/bin/env python3

"""This script segments an audio file into smaller files based on silent
periods. It uses ffmpeg for silence detection and audio processing.

Usage:
    python splitmp3.py input_file output_dir [-l segment_length]
        [-d min_silence_duration] [-t silence_threshold]

    input_file:        Path to the input audio file (e.g., abc.m4a).
    output_dir:        Path to the output directory (e.g., /tmp/foo).
    -l segment_length: Target segment length in seconds (default: 300
        seconds or 5 minutes).
    -d min_silence_duration: Minimum duration of silence to detect
        (default: 0.5 seconds).
    -t silence_threshold: Silence threshold in dB (default: -30 dB).

The script will create a subdirectory within the output directory named
after the input file, and then create the segments (as MP3 files), named
with zero-padded numbers like 001.mp3, 002.mp3, etc. If no silence is
detected it will create a single output file containing the entire audio
input.

Example:
    python splitmp3.py mybook.m4a /output -l 600 -d 0.3 -t -25

This example processes 'mybook.m4a', puts the output in '/output/mybook/',
and cuts it into segments of about 10min (-l 600) using silences of more
than 0.3 seconds (-d 0.3) when the sound drops to below -25dB (-t -25).
"""

import os
import subprocess
import argparse
"""
"""

def find_silent_periods(input_file, min_silence_duration=0.5,
                        silence_threshold=-30):
    """
    Finds silent periods in an audio file using ffmpeg.

    Args:
        input_file (str):             Path to the input audio file.
    
        min_silence_duration (float): Minimum duration of silence in
                                      seconds to consider.
    
        silence_threshold (int):      Silence threshold in dB.

    Returns:
        list: List of dictionaries, each with 'start' and 'end' timestamps
              of silent periods.
    """
    
    command = [
        "ffmpeg",
        "-i", input_file,
        "-af", f"silencedetect=noise={silence_threshold}dB:d={min_silence_duration}",
        "-f", "null",
        "-"
    ]
    
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                check=True)

        stderr_output = result.stderr

        start_time = None  # Track the most recent start time
        silence_periods = []
        
        for line in stderr_output.splitlines():
            if "silencedetect" in line:
                if "silence_start:" in line:
                    parts = line.split()
                    start_time = float(parts[parts.index("silence_start:") + 1])
                elif "silence_end:" in line and start_time is not None:
                    parts = line.split()
                    end_time = float(parts[parts.index("silence_end:") + 1])
                    silence_periods.append({"start": start_time,
                                            "end": end_time})
                    start_time = None # Reset for next segment

        return silence_periods
    except subprocess.CalledProcessError as e:
        print(f"Error during ffmpeg execution: {e}")
        print(f"  Stdout: {e.stdout}")
        print(f"  Stderr: {e.stderr}")
        return None

def create_segment(input_file, output_file, start_time, end_time=None):
    """
    Creates an audio segment using ffmpeg.

    Args:
        input_file (str):           Path to the input audio file.
    
        output_file (str):          Path to the output audio file.

        start_time (float):         Start time of the segment in seconds.

        end_time (float, optional): End time of the segment in seconds.
                                    If None, segment goes to end.
    """
    command = [
        "ffmpeg",
        "-ss", str(start_time),
        "-to", str(end_time),
        "-i", input_file,
        "-c:a", "libmp3lame",
        "-y", output_file,
    ]
    
    try:
        subprocess.run(command, check=True, capture_output=True)
        duration = (end_time if end_time is not None
                    else get_audio_duration(input_file)) - start_time
        print(f"Created segment: {output_file} ({duration:.2f}s)")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error creating segment: {e}")
        print(f"  Stderr: {e.stderr}")
        return False

def segment_audio(input_file, output_dir, target_segment_length=300,
                  min_silence_duration=0.5, silence_threshold=-30):
    """
    Segments an audio file into smaller files based on silent periods.

    Args:
        input_file (str):             Path to the input audio file.
    
        output_dir (str):             Path to the output directory.
    
        target_segment_length (int):  Target segment length in seconds.
    
        min_silence_duration (float): Minimum duration of silence in
                                      seconds to consider.
    
        silence_threshold (int):      Silence threshold in dB.
    """
    
    filename = os.path.splitext(os.path.basename(input_file))[0]
    output_subdir = os.path.join(output_dir, filename)
    os.makedirs(output_subdir, exist_ok=True)

    silence_periods = find_silent_periods(input_file, min_silence_duration,
                                          silence_threshold)
    if silence_periods is None:
        output_file = os.path.join(output_subdir, input_file, ".mp3")
        create_segment(input_file, output_file, 0,
                       get_audio_duration(input_file))
        return

    segment_start = 0
    segments = []

    for silence in silence_periods:
        if silence["end"] - segment_start >= target_segment_length * 0.8 :
            # Consider cutting only if more than 80% of target length
            segments.append((segment_start, silence["end"]))
            segment_start = silence["end"]
    
    # Handle the remaining part of the file (if any)
    if segment_start < get_audio_duration(input_file):
        segments.append((segment_start, get_audio_duration(input_file)))


    num_segments = len(segments) # number of segments
    num_digits = len(str(num_segments))  # How much to left pad output files

    for segment_num, (segment_start, segment_end) in enumerate(segments,
                                                               start=1):
        output_file = os.path.join(output_subdir,
                                   f"{segment_num:0{num_digits}d}.mp3")
        create_segment(input_file, output_file, segment_start, segment_end)
        
def get_audio_duration(input_file):
    """
    Retrieves the duration of an audio file using ffprobe.

    Args:
        input_file (str): Path to the input audio file.

    Returns:
        float: Duration of the audio file in seconds.
    """
    
    command = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        input_file
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                check=True)
        return float(result.stdout.strip())
    except subprocess.CalledProcessError as e:
        print(f"Error getting duration: {e}")
        print(f"  Stderr: {e.stderr}")
        return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Split audio file based on silence.")
    parser.add_argument("input_file", help="Path to the input audio file")
    parser.add_argument("output_dir", help="Path to the output directory")
    parser.add_argument("-l", "--segment_length", type=int, default=300,
                        help="Target segment length in seconds (default: 300)")
    parser.add_argument("-d", "--min_silence_duration", type=float, default=0.5,
                        help="Minimum silence duration to detect (default: 0.5)"
                        )
    parser.add_argument("-t", "--silence_threshold", type=int, default=-30,
                        help="Silence threshold in dB (default: -30)")
    
    args = parser.parse_args()

        
    if not args.input_file and not args.output_dir:
      print(__doc__) # Print the top-level docstring if no args are provided
    elif not args.input_file or not args.output_dir:
      print("Must provide both input file and output directory")
    else:
        segment_audio(args.input_file, args.output_dir, args.segment_length,
                      args.min_silence_duration, args.silence_threshold)
        
