import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

class AudioProcessor:
    def __init__(self):
        self.client = Groq(api_key=os.getenv('GROQ_API_KEY'))
        self.model = "whisper-large-v3"
    
    def transcribe_audio(self, audio_file_path: str, language: str = None) -> dict:
        """
        Transcribe audio file using Groq Whisper API
        
        Args:
            audio_file_path: Path to audio file
            language: Optional language code (e.g., 'en', 'es', 'fr')
        
        Returns:
            Dictionary with transcription and metadata
        """
        try:
            with open(audio_file_path, "rb") as file:
                # Create transcription
                transcription = self.client.audio.transcriptions.create(
                    file=(os.path.basename(audio_file_path), file.read()),
                    model=self.model,
                    response_format="verbose_json",
                    language=language,
                    temperature=0.0
                )
            
            return {
                "success": True,
                "text": transcription.text,
                "language": getattr(transcription, 'language', 'unknown'),
                "duration": getattr(transcription, 'duration', None)
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "text": None
            }
    
    def translate_audio(self, audio_file_path: str) -> dict:
        """
        Translate audio to English using Groq Whisper API
        
        Args:
            audio_file_path: Path to audio file
        
        Returns:
            Dictionary with translation and metadata
        """
        try:
            with open(audio_file_path, "rb") as file:
                # Create translation
                translation = self.client.audio.translations.create(
                    file=(os.path.basename(audio_file_path), file.read()),
                    model=self.model,
                    response_format="verbose_json",
                    temperature=0.0
                )
            
            return {
                "success": True,
                "text": translation.text,
                "source_language": getattr(translation, 'language', 'unknown'),
                "duration": getattr(translation, 'duration', None)
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "text": None
            }
    
    def process_voice_note(self, audio_file_path: str, detect_language: bool = True) -> dict:
        """
        Process voice note with automatic language detection
        
        Args:
            audio_file_path: Path to audio file
            detect_language: Whether to detect language automatically
        
        Returns:
            Dictionary with transcription results
        """
        # First, try to transcribe with auto-detect
        result = self.transcribe_audio(audio_file_path)
        
        if result["success"]:
            return {
                "success": True,
                "transcription": result["text"],
                "language": result.get("language", "unknown"),
                "duration": result.get("duration"),
                "method": "transcription"
            }
        else:
            # If transcription fails, try translation
            translation_result = self.translate_audio(audio_file_path)
            
            if translation_result["success"]:
                return {
                    "success": True,
                    "transcription": translation_result["text"],
                    "language": translation_result.get("source_language", "unknown"),
                    "duration": translation_result.get("duration"),
                    "method": "translation",
                    "note": "Translated to English"
                }
            else:
                return {
                    "success": False,
                    "error": translation_result.get("error", "Unknown error"),
                    "transcription": None
                }