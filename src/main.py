import os
import logging
import re
import datetime
import math
import uuid
import tempfile
import socket
import json
import requests
from requests_toolbelt import MultipartEncoder

from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.datastructures import UploadFile as StarletteUploadFile
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from typing import List, Optional, Dict, Any

import webvtt
from pydub import AudioSegment
# Fix MoviePy imports
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.VideoClip import ImageClip, TextClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip


# ---- 1) Local Transliteration Import (indic-transliteration) ----
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate as indic_transliterate

# ------------------------------------------------------------------------------
# IMPORTANT: API Keys and Constants
# ------------------------------------------------------------------------------
# Set your ElevenLabs API key here (or load from environment variable)
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_BASE_URL = "https://api.elevenlabs.io/v1"

import uvicorn
# ------------------------------------------------------------------------------
# Middleware for Max File Size
# ------------------------------------------------------------------------------
class MaxFileSizeMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI, max_size: int = 100 * 1024 * 1024):
        super().__init__(app)
        self.max_size = max_size

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        if request.method == "POST":
            if "content-length" in request.headers:
                try:
                    content_length = int(request.headers["content-length"])
                    if content_length > self.max_size:
                        return Response(
                            status_code=413,
                            content=f"File too large. Maximum size allowed is {self.max_size} bytes"
                        )
                except ValueError:
                    pass
        return await call_next(request)


# ------------------------------------------------------------------------------
# Setup logging
# ------------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# Utility: Parse SRT/WebVTT times
# ------------------------------------------------------------------------------
def parse_time(time_str: str) -> datetime.time:
    """Parse SRT timestamp string to datetime.time object."""
    try:
        # Split into hours, minutes, seconds, and milliseconds
        time_parts = re.split(r'[:.]', time_str)
        if len(time_parts) != 4:
            raise ValueError("Invalid time format")
        
        hours = int(time_parts[0])
        minutes = int(time_parts[1])
        seconds = int(time_parts[2])
        milliseconds = int(time_parts[3])
        
        # Create time object with milliseconds
        return datetime.time(hours, minutes, seconds, milliseconds // 1000)
    except Exception as e:
        logger.error(f"Error parsing time string '{time_str}': {str(e)}")
        return None
    
def seconds_to_srt_timestamp(seconds: float) -> str:
    """
    Convert a float number of seconds to an SRT/WebVTT timestamp: HH:MM:SS.mmm
    """
    td = datetime.timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    millis = int((td.total_seconds() - total_seconds) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


# ------------------------------------------------------------------------------
# Utility: Optimize Subtitles
# ------------------------------------------------------------------------------
def optimize_subtitles_for_timing(captions: List[webvtt.Caption]) -> List[webvtt.Caption]:
    """
    - Merge short captions
    - Add buffer time
    - Break up overly long lines
    """
    if not captions:
        return []

    MIN_DURATION = 1.0   # merge very short segments
    BUFFER_TIME = 0.2
    MAX_CHARS_PER_LINE = 60

    optimized_captions = []
    current_caption = None
    current_start_seconds = None
    current_end_seconds = None

    for caption in captions:
        start_time_obj = parse_time(caption.start)
        end_time_obj = parse_time(caption.end)
        if start_time_obj is None or end_time_obj is None:
            continue

        start_s = (start_time_obj.hour * 3600
                   + start_time_obj.minute * 60
                   + start_time_obj.second
                   + start_time_obj.microsecond / 1e6)
        end_s = (end_time_obj.hour * 3600
                 + end_time_obj.minute * 60
                 + end_time_obj.second
                 + end_time_obj.microsecond / 1e6)

        if end_s <= start_s:
            continue

        text = caption.text.strip()

        if current_caption:
            duration = current_end_seconds - current_start_seconds
            if duration < MIN_DURATION:
                # Merge with the current caption
                current_caption.text = f"{current_caption.text} {text}"
                current_end_seconds = end_s
                continue

            # Otherwise, finalize the current caption
            optimized_captions.append(
                webvtt.Caption(
                    seconds_to_srt_timestamp(current_start_seconds),
                    seconds_to_srt_timestamp(current_end_seconds),
                    current_caption.text
                )
            )
            current_caption = None

        if not current_caption:
            current_caption = caption
            current_start_seconds = start_s
            current_end_seconds = end_s

        # Add buffer from previous
        if optimized_captions:
            prev_end_obj = parse_time(optimized_captions[-1].end)
            if prev_end_obj:
                prev_end_s = (prev_end_obj.hour * 3600
                              + prev_end_obj.minute * 60
                              + prev_end_obj.second
                              + prev_end_obj.microsecond / 1e6)
                current_start_seconds = max(current_start_seconds, prev_end_s + BUFFER_TIME)

        # Split if line is too long
        if len(text) > MAX_CHARS_PER_LINE:
            words = text.split()
            lines = []
            tmp_line = ""
            for w in words:
                if len(tmp_line) + len(w) + 1 > MAX_CHARS_PER_LINE:
                    lines.append(tmp_line.strip())
                    tmp_line = ""
                tmp_line += w + " "
            lines.append(tmp_line.strip())
            current_caption.text = "\n".join(lines)

    # Final flush
    if current_caption:
        optimized_captions.append(
            webvtt.Caption(
                seconds_to_srt_timestamp(current_start_seconds),
                seconds_to_srt_timestamp(current_end_seconds),
                current_caption.text
            )
        )

    return optimized_captions


# ------------------------------------------------------------------------------
# Local Transliteration from Devanagari to Latin (ITRANS scheme)
# ------------------------------------------------------------------------------
def transliterate_hindi_to_latin(text: str) -> str:
    """
    Attempt to transliterate from Devanagari script to a Latin-based scheme (ITRANS).
    If text is already in Latin or contains no Devanagari, it should remain unaffected.
    """
    # Attempt a broad approach: everything recognized as Devanagari -> ITRANS
    # `indic_transliterate(...)` is somewhat naive if the text is partially English.
    # But for code simplicity, we pass the entire string.
    try:
        return indic_transliterate(text, sanscript.DEVANAGARI, sanscript.ITRANS)
    except Exception as e:
        logger.warning(f"Transliteration error, returning original text: {e}")
        return text


# ------------------------------------------------------------------------------
# Lyrics Processing Functions
# ------------------------------------------------------------------------------
def preprocess_lyrics(lyrics_text: str) -> List[str]:
    """
    Split raw lyrics text into lines/phrases for alignment.
    Removes empty lines and trims whitespace.
    Also filters out organization markers like 'Verse 1', 'Chorus', etc.
    """
    if not lyrics_text:
        return []
    
    # Split by newlines and filter empty lines
    lines = []
    for line in lyrics_text.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        # Skip organization markers
        if (line.upper().startswith("VERSE") or 
            line.upper().startswith("CHORUS") or 
            line.upper().startswith("BRIDGE") or
            (line.isupper() and len(line) < 15)):
            continue
            
        lines.append(line)
    
    return lines


# ------------------------------------------------------------------------------
# ElevenLabs Speech-to-Text (Scribe) Integration
# ------------------------------------------------------------------------------
def transcribe_audio_with_elevenlabs(
    audio_path: str,
    language: Optional[str] = None,
    model_id: Optional[str] = "scribe_v1"  # Change to scribe_v1, the only available STT model
) -> dict:
    """
    Transcribe audio using ElevenLabs Scribe API.
    
    Args:
        audio_path: Path to the audio file
        language: Optional language code (ISO 639-1)
        model_id: Model ID to use (defaults to "scribe_v1")
        
    Returns:
        Complete response from ElevenLabs API containing text, words with timestamps, etc.
    """
    # Check if API key is available
    if not ELEVENLABS_API_KEY:
        logger.error("⚠️ ElevenLabs API key not found or empty. Cannot use ElevenLabs Scribe.")
        logger.error("Please set ELEVENLABS_API_KEY environment variable or update the value in the code.")
        raise ValueError("ElevenLabs API key is required for transcription. Please set ELEVENLABS_API_KEY.")
    else:
        logger.info(f"✓ ElevenLabs API key found (length: {len(ELEVENLABS_API_KEY)})")
    
    url = f"{ELEVENLABS_BASE_URL}/speech-to-text"
    file_size = os.path.getsize(audio_path) / (1024 * 1024)  # Size in MB
    
    logger.info(f"Preparing to transcribe audio with ElevenLabs Scribe API:")
    logger.info(f"  - File: {os.path.basename(audio_path)} ({file_size:.2f} MB)")
    logger.info(f"  - Language: {language if language else 'auto-detect'}")
    logger.info(f"  - Model ID: {model_id}")
    
    # Prepare the file for upload
    with open(audio_path, 'rb') as f:
        # Setup the multipart form data
        fields = {
            'file': (os.path.basename(audio_path), f, 'audio/mpeg'),
            'model_id': model_id  # Always include model_id as it's required
        }
        
        # Add optional parameters if specified
        if language:
            fields['language'] = language
        
        multipart_data = MultipartEncoder(fields=fields)
        
        # Set up headers with API key and content type
        headers = {
            'Accept': 'application/json',
            'xi-api-key': ELEVENLABS_API_KEY,
            'Content-Type': multipart_data.content_type
        }
        
        # Make the API request
        try:
            logger.info(f"🚀 Sending request to ElevenLabs Scribe API...")
            response = requests.post(url, headers=headers, data=multipart_data)
            
            # Handle different error codes
            if response.status_code == 200:
                logger.info(f"✓ ElevenLabs Scribe API request successful!")
            elif response.status_code == 401:
                logger.error("❌ Authentication failed. Check your ElevenLabs API key.")
                logger.error(f"Response: {response.text}")
                raise ValueError("Invalid ElevenLabs API key")
            elif response.status_code == 429:
                logger.error("❌ Rate limit exceeded or quota exhausted.")
                logger.error(f"Response: {response.text}")
                raise ValueError("ElevenLabs API rate limit exceeded or quota exhausted")
            else:
                logger.error(f"❌ ElevenLabs API returned status code {response.status_code}")
                logger.error(f"Response: {response.text}")
                response.raise_for_status()
            
            result = response.json()
            
            # Log some info about the result
            if 'text' in result:
                text_preview = result['text'][:100] + '...' if len(result['text']) > 100 else result['text']
                logger.info(f"✓ Transcription received: \"{text_preview}\"")
            
            if 'words' in result:
                logger.info(f"✓ Received timing information for {len(result['words'])} words/tokens")
            else:
                logger.warning("⚠️ No word-level timing information in the response")
            
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error calling ElevenLabs API: {str(e)}")
            if 'response' in locals() and response is not None:
                logger.error(f"Response status: {response.status_code}")
                logger.error(f"Response content: {response.text}")
            raise ValueError(f"Failed to transcribe audio with ElevenLabs: {str(e)}")


def elevenlabs_to_webvtt(elevenlabs_response: dict, transliterate: bool = True) -> webvtt.WebVTT:
    """
    Convert ElevenLabs Scribe API response to WebVTT format.
    
    Args:
        elevenlabs_response: Response from ElevenLabs Scribe API
        transliterate: Whether to transliterate non-Latin scripts to Latin
        
    Returns:
        WebVTT object with all captions
    """
    vtt = webvtt.WebVTT()
    
    # Extract all words (except spacing) with their timestamps
    words = [w for w in elevenlabs_response.get("words", []) if w.get("type") == "word"]
    
    # Skip filtering organizational texts for direct transcription to preserve more of the transcription
    # We want to keep as much of the ElevenLabs transcription as possible
    
    # Group words into sentences based on timing gaps and punctuation
    sentences = []
    current_sentence = []
    
    for i, word in enumerate(words):
        current_sentence.append(word)
        
        # Check if this word ends with punctuation
        text = word.get("text", "")
        if text.endswith((".", "!", "?", ",", ":", ";")) or i == len(words) - 1:
            # End of sentence
            if current_sentence:
                sentences.append(current_sentence)
                current_sentence = []
        
        # Also check for timing gaps (if more than 0.7 second gap to next word)
        elif i < len(words) - 1:
            current_end = word.get("end", 0)
            next_start = words[i+1].get("start", 0)
            if next_start - current_end > 0.7:
                # Gap between words, end the sentence
                if current_sentence:
                    sentences.append(current_sentence)
                    current_sentence = []
    
    # Add the last sentence if it's not empty
    if current_sentence:
        sentences.append(current_sentence)
    
    # Convert each sentence to a WebVTT caption
    for sentence in sentences:
        if not sentence:
            continue
            
        # Get start and end times for the sentence
        start_time = sentence[0].get("start", 0)
        end_time = sentence[-1].get("end", 0)
        
        # Combine the text
        text = " ".join(word.get("text", "") for word in sentence)
        
        # Apply transliteration if needed
        if transliterate:
            # Check if the text contains Devanagari (or other non-Latin scripts)
            if any(ord(c) > 127 for c in text):
                text = transliterate_hindi_to_latin(text)
        
        # Create the caption
        start_str = seconds_to_srt_timestamp(start_time)
        end_str = seconds_to_srt_timestamp(end_time)
        
        # Ensure minimum duration (1 second)
        start_seconds = parse_seconds_from_timestamp(start_str)
        end_seconds = parse_seconds_from_timestamp(end_str)
        if end_seconds - start_seconds < 1.0:
            end_seconds = start_seconds + 1.0
            end_str = seconds_to_srt_timestamp(end_seconds)
        
        vtt.captions.append(webvtt.Caption(start_str, end_str, text))
    
    return vtt

def parse_seconds_from_timestamp(timestamp: str) -> float:
    """Converts a timestamp string (HH:MM:SS.mmm) to seconds"""
    time_parts = timestamp.split(':')
    if len(time_parts) != 3:
        return 0.0
    
    hours = int(time_parts[0])
    minutes = int(time_parts[1])
    seconds_parts = time_parts[2].split('.')
    seconds = int(seconds_parts[0])
    milliseconds = int(seconds_parts[1]) if len(seconds_parts) > 1 else 0
    
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000


def align_lyrics_with_scribe(
    lyrics_lines: List[str],
    audio_duration: float
) -> List[dict]:
    """
    Evenly distribute lyrics across the audio duration when only lyrics are provided.
    
    Args:
        lyrics_lines: List of lyrics lines
        audio_duration: Total duration of the audio in seconds
        
    Returns:
        List of dicts with 'start', 'end', 'text' using provided lyrics
    """
    if not lyrics_lines or audio_duration <= 0:
        return []
    
    # Filter out organization markers like 'Verse 1', 'Chorus', etc.
    filtered_lyrics = []
    for line in lyrics_lines:
        if (line.upper().startswith("VERSE") or 
            line.upper().startswith("CHORUS") or 
            line.upper().startswith("BRIDGE") or
            (line.isupper() and len(line) < 15)):
            continue
        filtered_lyrics.append(line)
    
    # Evenly distribute the lyrics across the audio duration
    time_per_line = audio_duration / len(filtered_lyrics)
    aligned_segments = []
    
    for i, line in enumerate(filtered_lyrics):
        start_time = i * time_per_line
        end_time = (i + 1) * time_per_line
        
        aligned_segments.append({
            'start': start_time,
            'end': end_time,
            'text': line
        })
    
    return aligned_segments


def align_lyrics_with_words(
    lyrics_lines: List[str], 
    word_timings: List[dict],
    audio_duration: float
) -> List[dict]:
    """
    Perform fine-grained word-level alignment between provided lyrics and transcribed words.
    Uses a more robust approach to match words.
    
    Args:
        lyrics_lines: List of lyrics lines to align
        word_timings: List of word objects from ElevenLabs with timing info
        audio_duration: Duration of the audio in seconds
        
    Returns:
        List of dicts with 'start', 'end', 'text' for each aligned segment
        Returns an empty list if no matches were found (to trigger using ElevenLabs transcription)
    """
    if not lyrics_lines or not word_timings or audio_duration <= 0:
        return []
    
    logger.info(f"Starting improved alignment with {len(lyrics_lines)} lines and {len(word_timings)} transcribed words")
    
    # Normalize both lyrics and transcribed words for better matching
    # Join all lyrics into a single text and prepare for matching
    normalized_lyrics_lines = []
    for line in lyrics_lines:
        # Normalize: lowercase, remove punctuation, excess whitespace
        norm_line = re.sub(r'[^\w\s]', '', line.lower()).strip()
        if norm_line:  # Skip empty lines
            normalized_lyrics_lines.append({
                'text': norm_line,
                'original': line
            })
    
    # Normalize transcribed words 
    normalized_transcribed_words = []
    current_sentence = []
    current_start = None
    current_end = None
    
    # Group transcribed words into sentences for better matching with lyrics lines
    for word in word_timings:
        if not word.get('text', '').strip():
            continue
            
        # Clean and normalize word
        norm_word = re.sub(r'[^\w\s]', '', word.get('text', '').lower()).strip()
        if not norm_word:
            continue
            
        if current_start is None:
            current_start = word.get('start', 0)
            
        current_sentence.append(norm_word)
        current_end = word.get('end', 0)
        
        # End sentence at punctuation or significant pause
        if (word.get('text', '').rstrip()[-1] in '.!?') or (
                len(current_sentence) > 10):  # Reasonable sentence length
            
            if current_sentence:
                normalized_transcribed_words.append({
                    'text': ' '.join(current_sentence),
                    'start': current_start,
                    'end': current_end
                })
                current_sentence = []
                current_start = None
    
    # Add any remaining words as a sentence
    if current_sentence and current_start is not None:
        normalized_transcribed_words.append({
            'text': ' '.join(current_sentence),
            'start': current_start,
            'end': current_end or audio_duration
        })
    
    logger.info(f"Normalized to {len(normalized_lyrics_lines)} lyrics lines and {len(normalized_transcribed_words)} transcribed segments")
    
    # If we have very few transcribed segments, use more granular approach
    if len(normalized_transcribed_words) < len(normalized_lyrics_lines) / 2:
        logger.warning("Too few transcribed segments. Using word-by-word approach.")
        # Rebuild the transcribed words array at word level, not sentence level
        normalized_transcribed_words = []
        for word in word_timings:
            if not word.get('text', '').strip():
                continue
                
            norm_word = re.sub(r'[^\w\s]', '', word.get('text', '').lower()).strip()
            if norm_word:
                normalized_transcribed_words.append({
                    'text': norm_word,
                    'start': word.get('start', 0),
                    'end': word.get('end', 0)
                })
    
    # First try to match entire lines
    aligned_segments = []
    used_transcribed_indices = set()
    match_count = 0
    
    # For each lyrics line, find the best matching transcribed segment
    for lyrics_idx, lyrics_line in enumerate(normalized_lyrics_lines):
        best_match_idx = -1
        best_match_score = 0
        
        for trans_idx, trans_segment in enumerate(normalized_transcribed_words):
            if trans_idx in used_transcribed_indices:
                continue
                
            # Calculate similarity score (simple for now, can be improved)
            lyrics_words = set(lyrics_line['text'].split())
            trans_words = set(trans_segment['text'].split())
            
            # Intersection over union for word sets
            if not lyrics_words or not trans_words:
                continue
                
            common_words = len(lyrics_words.intersection(trans_words))
            total_words = len(lyrics_words.union(trans_words))
            
            if total_words == 0:
                continue
                
            similarity = common_words / total_words
            
            # Save best matching segment
            if similarity > best_match_score and similarity > 0.3:  # Minimum threshold
                best_match_score = similarity
                best_match_idx = trans_idx
        
        if best_match_idx >= 0:
            # Add this match
            trans_segment = normalized_transcribed_words[best_match_idx]
            aligned_segments.append({
                'start': trans_segment['start'],
                'end': trans_segment['end'],
                'text': lyrics_line['original'],
                'match_score': best_match_score
            })
            used_transcribed_indices.add(best_match_idx)
            match_count += 1
            logger.info(f"Matched line {lyrics_idx+1}: '{lyrics_line['original'][:30]}...' with score {best_match_score:.2f}")
        else:
            logger.warning(f"No match found for line {lyrics_idx+1}: '{lyrics_line['original'][:30]}...'")
    
    # Log match success rate
    success_rate = (match_count / len(normalized_lyrics_lines)) * 100 if normalized_lyrics_lines else 0
    logger.info(f"Match success rate: {success_rate:.1f}% ({match_count}/{len(normalized_lyrics_lines)} lines matched)")
    
    # If almost no matches were found, return empty list to trigger using ElevenLabs transcription directly
    if success_rate < 10 and len(normalized_lyrics_lines) > 5:
        logger.warning("⚠️ Very low match rate detected. Will use ElevenLabs transcription directly.")
        return []
    
    # Only continue with gap filling if we have at least some matches
    if match_count > 0:
        # For unmatched lyrics lines, distribute among the gaps
        unmatched_indices = [i for i in range(len(normalized_lyrics_lines)) 
                            if i not in [lyrics_lines.index(s['text']) for s in aligned_segments 
                                        if s['text'] in lyrics_lines]]
        
        if unmatched_indices and aligned_segments:
            logger.info(f"Distributing {len(unmatched_indices)} unmatched lines")
            
            # Sort aligned segments by start time
            aligned_segments.sort(key=lambda x: x['start'])
            
            # Find gaps
            gaps = []
            # Gap at the beginning?
            if aligned_segments[0]['start'] > 1.0:
                gaps.append({
                    'start': 0,
                    'end': aligned_segments[0]['start'],
                    'duration': aligned_segments[0]['start']
                })
            
            # Gaps between segments
            for i in range(1, len(aligned_segments)):
                gap_start = aligned_segments[i-1]['end']
                gap_end = aligned_segments[i]['start']
                duration = gap_end - gap_start
                
                if duration > 0.5:  # Only consider gaps over 0.5 seconds
                    gaps.append({
                        'start': gap_start,
                        'end': gap_end,
                        'duration': duration
                    })
            
            # Gap at the end?
            if aligned_segments[-1]['end'] < audio_duration - 1.0:
                gaps.append({
                    'start': aligned_segments[-1]['end'],
                    'end': audio_duration,
                    'duration': audio_duration - aligned_segments[-1]['end']
                })
            
            # If we have gaps, distribute unmatched lines
            if gaps:
                # Sort gaps by duration (largest first)
                gaps.sort(key=lambda x: x['duration'], reverse=True)
                
                # Distribute unmatched lines across gaps, prioritizing larger gaps
                remaining_lines = [normalized_lyrics_lines[i]['original'] for i in unmatched_indices]
                
                # Optimized distribution algorithm
                if len(remaining_lines) <= len(gaps):
                    # One line per gap, starting with largest gaps
                    for i, line in enumerate(remaining_lines):
                        if i < len(gaps):
                            gap = gaps[i]
                            aligned_segments.append({
                                'start': gap['start'],
                                'end': gap['end'],
                                'text': line,
                                'match_score': 0  # Indicate this was gap-filled
                            })
                else:
                    # Multiple lines per gap
                    total_gap_duration = sum(g['duration'] for g in gaps)
                    time_per_line = total_gap_duration / len(remaining_lines)
                    
                    line_index = 0
                    for gap in gaps:
                        # How many lines can fit in this gap?
                        lines_in_gap = max(1, int(gap['duration'] / time_per_line))
                        lines_in_gap = min(lines_in_gap, len(remaining_lines) - line_index)
                        
                        if lines_in_gap <= 0:
                            continue
                        
                        time_per_line_in_gap = gap['duration'] / lines_in_gap
                        
                        for i in range(lines_in_gap):
                            if line_index < len(remaining_lines):
                                start_time = gap['start'] + i * time_per_line_in_gap
                                end_time = start_time + time_per_line_in_gap
                            
                                aligned_segments.append({
                                    'start': start_time,
                                    'end': end_time,
                                    'text': remaining_lines[line_index],
                                    'match_score': 0  # Indicate this was gap-filled
                                })
                                line_index += 1
    
    # If we still have no aligned segments at all, return empty list to trigger using ElevenLabs transcription
    if not aligned_segments:
        logger.warning("No successful matches found. Will use ElevenLabs transcription directly.")
        return []
    
    # Final sort by start time
    aligned_segments.sort(key=lambda x: x['start'])
    
    # Remove any overlaps
    for i in range(1, len(aligned_segments)):
        if aligned_segments[i]['start'] < aligned_segments[i-1]['end']:
            aligned_segments[i]['start'] = aligned_segments[i-1]['end']
            
    # Log final alignment for debugging
    logger.info(f"Final alignment: {len(aligned_segments)} segments")
    for i, segment in enumerate(aligned_segments[:5]):  # Log first 5 segments
        logger.info(f"  {i+1}. {segment['start']:.2f}s - {segment['end']:.2f}s: '{segment['text'][:30]}...'")
    if len(aligned_segments) > 5:
        logger.info(f"  ... and {len(aligned_segments)-5} more segments")
    
    return aligned_segments


def transcribe_and_align_lyrics(
    audio_path: str,
    lyrics_text: str,
    language: Optional[str] = None,
    alignment_mode: str = 'auto'
) -> webvtt.WebVTT:
    """
    1) If ElevenLabs API key is available:
       - Use ElevenLabs Scribe to get timing information
       - If mode is 'elevenlabs', use ElevenLabs transcription directly
       - If mode is 'auto', attempt to align with provided lyrics
       - If alignment fails or match rate is low, use ElevenLabs transcription directly
    2) If no ElevenLabs API key or transcription fails:
       - Only then fall back to evenly distributing lyrics across audio duration
    
    Args:
        audio_path: Path to the audio file
        lyrics_text: Raw lyrics text
        language: Optional language code
        alignment_mode: 'auto', 'elevenlabs', or 'even'
        
    Returns:
        WebVTT object with aligned lyrics
    """
    # Process lyrics into lines
    lyrics_lines = preprocess_lyrics(lyrics_text)
    if not lyrics_lines:
        logger.warning("⚠️ No valid lyrics provided. Cannot create subtitles.")
        raise ValueError("Valid lyrics are required. Please provide lyrics text.")
    
    logger.info(f"✓ Processed lyrics text into {len(lyrics_lines)} lines")
    
    # Get audio duration for alignment
    try:
        audio_clip = AudioFileClip(audio_path)
        audio_duration = audio_clip.duration
        audio_clip.close()
        logger.info(f"✓ Audio duration: {audio_duration:.2f} seconds")
    except Exception as e:
        logger.error(f"❌ Error getting audio duration: {e}")
        raise ValueError(f"Could not determine audio duration: {str(e)}")
    
    try:
        # First try using ElevenLabs Scribe for precise timing
        if ELEVENLABS_API_KEY:
            logger.info("Attempting to use ElevenLabs Scribe for transcription and alignment...")
            
            elevenlabs_response = transcribe_audio_with_elevenlabs(audio_path, language)
            
            if elevenlabs_response and 'words' in elevenlabs_response:
                # If mode is 'elevenlabs', use ElevenLabs transcription directly
                if alignment_mode == 'elevenlabs':
                    logger.info("Using ElevenLabs transcription directly as specified by alignment_mode='elevenlabs'")
                    vtt = elevenlabs_to_webvtt(elevenlabs_response, transliterate=False)
                    logger.info(f"✓ Created WebVTT with {len(vtt.captions)} captions using ElevenLabs transcription")
                    return vtt
                
                # Extract all words with timing
                word_timings = [w for w in elevenlabs_response.get("words", []) 
                               if w.get("type") == "word"]
                
                logger.info(f"✓ Using fine-grained word alignment with {len(word_timings)} transcribed words")
                
                # Log a sample of words for debugging
                if word_timings:
                    logger.info("Sample words with timing (first 3):")
                    for i, word in enumerate(word_timings[:3]):
                        logger.info(f"  {i+1}. '{word.get('text', '')}' at {word.get('start', 0):.2f}s - {word.get('end', 0):.2f}s")
                
                # Try to align provided lyrics with the transcribed words
                aligned_segments = align_lyrics_with_words(lyrics_lines, word_timings, audio_duration)
                
                # If alignment failed or returned empty list (low match rate), use ElevenLabs directly
                if not aligned_segments:
                    logger.warning("⚠️ No successful matches between provided lyrics and transcription.")
                    logger.warning("⚠️ Using ElevenLabs transcription text directly for better timing.")
                    
                    # Convert ElevenLabs response directly to WebVTT
                    vtt = elevenlabs_to_webvtt(elevenlabs_response, transliterate=False)
                    logger.info(f"✓ Created WebVTT with {len(vtt.captions)} captions using ElevenLabs transcription")
                    return vtt
                else:
                    logger.info(f"✓ Successfully aligned {len(aligned_segments)} lyrics segments using ElevenLabs timing")
                    
                    # Convert to WebVTT
                    vtt = webvtt.WebVTT()
                    for s in aligned_segments:
                        start_str = seconds_to_srt_timestamp(s["start"])
                        end_str = seconds_to_srt_timestamp(s["end"])
                        vtt.captions.append(webvtt.Caption(start_str, end_str, s["text"]))
                    
                    logger.info(f"✓ Created WebVTT with {len(vtt.captions)} captions")
                    return vtt
        else:
            logger.warning("⚠️ No ElevenLabs API key available, skipping Scribe transcription")
    
    except Exception as e:
        logger.error(f"❌ Error using ElevenLabs Scribe for alignment: {str(e)}")
        logger.info("Falling back to simple timing distribution")
    
    # Fallback (last resort): evenly distribute lyrics across the audio duration
    if alignment_mode == 'even':
        logger.info("Using even distribution as specified by alignment_mode='even'")
    else:
        logger.warning("⚠️ LAST RESORT: Using fallback method of evenly distributing lyrics across audio duration")
        logger.warning("⚠️ This may result in poor sync between audio and subtitles")
    
    aligned_segments = align_lyrics_with_scribe(lyrics_lines, audio_duration)
    logger.info(f"✓ Created {len(aligned_segments)} evenly distributed lyrics segments")

    # Convert to WebVTT
    vtt = webvtt.WebVTT()
    for s in aligned_segments:
        start_str = seconds_to_srt_timestamp(s["start"])
        end_str = seconds_to_srt_timestamp(s["end"])
        vtt.captions.append(webvtt.Caption(start_str, end_str, s["text"]))

    return vtt


# ------------------------------------------------------------------------------
# FastAPI Setup
# ------------------------------------------------------------------------------
app = FastAPI()

# Increase internal spool size
StarletteUploadFile.spool_max_size = 1024 * 1024 * 100

# Mount static files directory if you need it
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

# 100MB limit
app.add_middleware(MaxFileSizeMiddleware, max_size=100 * 1024 * 1024)
app.state.max_upload_size = 100 * 1024 * 1024  # 100 MB


async def save_upload_file(upload_file: UploadFile, destination: str) -> bool:
    """
    Save an uploaded file in chunks to disk.
    """
    try:
        CHUNK_SIZE = 1024 * 1024
        with open(destination, "wb") as f:
            while True:
                chunk = await upload_file.read(CHUNK_SIZE)
                if not chunk:
                    break
                f.write(chunk)
        return True
    except Exception as e:
        logger.error(f"Error saving {upload_file.filename} to {destination}: {e}")
        return False


# ------------------------------------------------------------------------------
# Main Endpoint: /create-video
# ------------------------------------------------------------------------------
@app.post("/create-video")
async def create_video(
    image: UploadFile = File(..., description="Image file (JPEG/PNG)"),
    audio: UploadFile = File(..., description="Audio file (MP3/WAV/FLAC)"),
    lyrics: Optional[str] = Form(default=None, description="Optional lyrics text for alignment"),
    language: Optional[str] = Form(default=None, description="Language code (e.g., 'en', 'hi', etc.)"),
    font_size: Optional[int] = Form(default=45, description="Font size for subtitles"),
    font_color: Optional[str] = Form(default="yellow", description="Font color for subtitles"),
    words_per_group: Optional[int] = Form(default=3, description="Number of words to show together"),
    timing_offset: Optional[float] = Form(default=0.0, description="Global timing offset in seconds"),
    min_duration: Optional[float] = Form(default=1.0, description="Minimum duration for each subtitle in seconds"),
    alignment_mode: Optional[str] = Form(default="auto", description="Alignment mode: 'auto', 'elevenlabs', or 'even'"),
    debug_mode: Optional[bool] = Form(default=False, description="Enable debug mode with timing information")
):
    """
    Create a video with a static image background + audio + subtitles.
    
    If lyrics are provided, they will be aligned with the audio timing using ElevenLabs Scribe.
    The alignment uses fine-grained word matching for better accuracy.
    If ElevenLabs API key is not available or transcription fails, the lyrics will be evenly distributed.
    
    Parameters:
    - timing_offset: Shift all subtitles by this many seconds (+ or -)
    - min_duration: Minimum time each subtitle should be visible
    - alignment_mode: Control how lyrics are aligned with audio
    - debug_mode: Add timing information to subtitles for debugging
    """
    logger.info("=== /create-video endpoint hit ===")
    try:
        logger.info("=== /create-video called ===")
        logger.info(f"Image: {image.filename}")
        logger.info(f"Audio: {audio.filename}")
        logger.info(f"Language: {language if language else 'Not specified'}")
        logger.info(f"Timing offset: {timing_offset} seconds")
        logger.info(f"Min duration: {min_duration} seconds")
        logger.info(f"Alignment mode: {alignment_mode}")
        logger.info(f"Font settings: size={font_size}, color={font_color}, words_per_group={words_per_group}")
        logger.info(f"Debug mode: {'Enabled' if debug_mode else 'Disabled'}")
        
        lyrics_provided = lyrics is not None and lyrics.strip() != ""
        logger.info(f"Lyrics Provided?: {'Yes' if lyrics_provided else 'No'}")
        
        if not lyrics_provided:
            logger.error("No lyrics provided in request")
            raise HTTPException(status_code=400, detail="Lyrics text is required. Please provide lyrics.")

        # 1) Validate & save input files
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)

        img_ext = os.path.splitext(image.filename)[1].lower()
        if img_ext not in [".jpg", ".jpeg", ".png"]:
            logger.error(f"Invalid image format: {img_ext}")
            raise HTTPException(status_code=400, detail="Image must be JPG or PNG.")

        aud_ext = os.path.splitext(audio.filename)[1].lower()
        if aud_ext not in [".mp3", ".wav", ".flac"]:
            logger.error(f"Invalid audio format: {aud_ext}")
            raise HTTPException(status_code=400, detail="Audio must be MP3, WAV, or FLAC.")

        image_path = os.path.join(output_dir, f"bg_image{img_ext}")
        audio_path = os.path.join(output_dir, f"bg_audio{aud_ext}")

        if not await save_upload_file(image, image_path):
            logger.error(f"Failed to save image file: {image_path}")
            raise HTTPException(status_code=500, detail=f"Failed to save image: {image_path}")
        
        if not await save_upload_file(audio, audio_path):
            logger.error(f"Failed to save audio file: {audio_path}")
            raise HTTPException(status_code=500, detail=f"Failed to save audio: {audio_path}")

        logger.info(f"✓ Successfully saved input files")

        # 2) Load audio to get duration
        audio_clip = AudioFileClip(audio_path)
        duration = audio_clip.duration
        logger.info(f"✓ Loaded audio clip, duration: {duration:.2f} seconds")

        # 3) Create background image clip for entire audio duration
        bg_clip = ImageClip(image_path).with_duration(duration)
        logger.info(f"✓ Created background image clip")

        # 4) Transcribe or align lyrics with improved word-level matching
        logger.info("Processing lyrics and audio...")
        
        # Handle alignment mode selection
        if alignment_mode == "elevenlabs" and not ELEVENLABS_API_KEY:
            logger.warning("ElevenLabs alignment mode selected but API key not available. Falling back to 'auto'.")
            alignment_mode = "auto"
        
        if alignment_mode == "even":
            # Manually evenly distribute lyrics
            audio_clip = AudioFileClip(audio_path)
            audio_duration = audio_clip.duration
            audio_clip.close()
            
            lyrics_lines = preprocess_lyrics(lyrics)
            aligned_segments = align_lyrics_with_scribe(lyrics_lines, audio_duration)
            
            # Convert to WebVTT
            vtt = webvtt.WebVTT()
            for s in aligned_segments:
                start_str = seconds_to_srt_timestamp(s["start"])
                end_str = seconds_to_srt_timestamp(s["end"])
                vtt.captions.append(webvtt.Caption(start_str, end_str, s["text"]))
        else:
            # Use automatic or forced ElevenLabs alignment
            vtt = transcribe_and_align_lyrics(
                audio_path,
                lyrics,
                language=language,
                alignment_mode=alignment_mode
            )
        
        logger.info(f"✓ Generated subtitles with {len(vtt.captions)} captions")

        # 5) Optimize subtitles
        optimized = optimize_subtitles_for_timing(vtt.captions)
        
        # Ensure minimum duration for each subtitle
        for i in range(len(optimized)):
            start_obj = parse_time(optimized[i].start)
            end_obj = parse_time(optimized[i].end)
            
            start_s = (start_obj.hour * 3600 + start_obj.minute * 60 + 
                       start_obj.second + start_obj.microsecond / 1e6)
            end_s = (end_obj.hour * 3600 + end_obj.minute * 60 + 
                     end_obj.second + end_obj.microsecond / 1e6)
            
            # Apply minimum duration
            if end_s - start_s < min_duration:
                end_s = start_s + min_duration
                optimized[i].end = seconds_to_srt_timestamp(end_s)
            
            # Fix any overlaps with next caption
            if i < len(optimized) - 1:
                next_start_obj = parse_time(optimized[i+1].start)
                next_start_s = (next_start_obj.hour * 3600 + next_start_obj.minute * 60 + 
                               next_start_obj.second + next_start_obj.microsecond / 1e6)
                
                if end_s > next_start_s:
                    # If this would make the caption too short, adjust the next one instead
                    if next_start_s - start_s >= min_duration:
                        optimized[i].end = seconds_to_srt_timestamp(next_start_s)
                    else:
                        optimized[i+1].start = seconds_to_srt_timestamp(end_s)
        
        logger.info(f"✓ Optimized subtitles: {len(optimized)} captions after optimization")

        # 6) Create subtitle text clips
        subtitle_clips = []
        for cap in optimized:
            start_obj = parse_time(cap.start)
            end_obj = parse_time(cap.end)
            if not start_obj or not end_obj:
                continue

            start_s = (start_obj.hour * 3600
                       + start_obj.minute * 60
                       + start_obj.second
                       + start_obj.microsecond / 1e6)
            end_s = (end_obj.hour * 3600
                     + end_obj.minute * 60
                     + end_obj.second
                     + end_obj.microsecond / 1e6)
            
            # Apply global timing offset if specified
            start_s += timing_offset
            end_s += timing_offset
            
            # Ensure start time is not negative
            start_s = max(0, start_s)
            # Ensure end time does not exceed video duration
            end_s = min(duration, end_s)
            
            sub_duration = end_s - start_s
            if sub_duration <= 0:
                continue

            # Split caption text into words and create clips for N words at a time
            words = cap.text.split()
            word_groups = []
            
            # Group words into chunks of specified size
            for i in range(0, len(words), words_per_group):
                group = words[i:min(i+words_per_group, len(words))]
                word_groups.append(" ".join(group))
            
            # Calculate timing for each word group
            if word_groups:
                time_per_group = sub_duration / len(word_groups)
                
                for i, group_text in enumerate(word_groups):
                    group_start = start_s + (i * time_per_group)
                    
                    # Add timing debug info if requested
                    if debug_mode:
                        group_text = f"[{group_start:.1f}s] {group_text}"
                    
                    # Create text clip for this group of words with improved visual styling
                    txt_clip = TextClip(
                        # Use FreeSans which has good Indic script support
                        font="/usr/share/fonts/truetype/freefont/FreeSans.ttf",
                        text=group_text,
                        font_size=font_size,
                        color=font_color,
                        bg_color=(0, 0, 0, 120),  # More opaque background for better readability
                        size=(700, 100),  # Larger text box
                        stroke_color='black',
                        stroke_width=2,  # Thicker stroke for better contrast
                        method='caption'
                    ).with_duration(time_per_group).with_start(group_start).with_position(("center", 0.8), relative=True)
                    
                    subtitle_clips.append(txt_clip)

        logger.info(f"✓ Created {len(subtitle_clips)} text clips for subtitles")

        # 7) Combine background + subtitles + audio
        final_clip = CompositeVideoClip([bg_clip] + subtitle_clips)
        final_clip.audio = audio_clip
        logger.info(f"✓ Combined image, subtitles, and audio into final clip")

        # 8) Write final video
        output_video = os.path.join(output_dir, "output.mp4")
        logger.info(f"Writing final video to {output_video}...")
        final_clip.write_videofile(
            output_video,
            fps=25,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile=os.path.join(output_dir, "temp-audio.m4a"),
            remove_temp=True
        )

        logger.info("✅ Video creation successful. Returning output.mp4.")
        return FileResponse(output_video, media_type="video/mp4", filename="output.mp4")

    except Exception as e:
        logger.error(f"❌ Error in /create-video: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------------------------
# Launch Uvicorn when script is run directly
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    import socket

    def find_free_port(start_port=8001, max_port=8020):
        for port in range(start_port, max_port + 1):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('0.0.0.0', port))
                    return port
            except OSError:
                continue
        raise OSError("No free ports found in range")

    port = find_free_port()
    logger.info(f"Starting server on port {port}")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        timeout_keep_alive=120
    )
