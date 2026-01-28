import os
import google.generativeai as genai
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

class ImageAnalyzer:
    def __init__(self):
        self.api_key = os.getenv('GEMINI_API_KEY')
        genai.configure(api_key=self.api_key)
        
        # Use Gemini Pro Vision
        self.model = genai.GenerativeModel('gemini-2.5-flash')
    
    def analyze_image(self, image_path: str, custom_prompt: str = None) -> str:
        """Analyze an image using Gemini API"""
        try:
            # Open and prepare image
            img = Image.open(image_path)
            
            # Default prompt if none provided
            if custom_prompt is None:
                prompt = """Analyze this image in detail. Describe:
1. What you see in the image
2. Main objects, people, or elements
3. The setting or context
4. Any text or notable details
5. Overall mood or atmosphere

Be descriptive and specific."""
            else:
                prompt = custom_prompt
            
            # Generate content
            response = self.model.generate_content([prompt, img])
            
            return response.text
        
        except Exception as e:
            return f"Error analyzing image: {str(e)}"
    
    def answer_question_about_image(self, image_path: str, question: str) -> str:
        """Answer a specific question about an image"""
        try:
            img = Image.open(image_path)
            
            prompt = f"Based on this image, please answer the following question: {question}"
            
            response = self.model.generate_content([prompt, img])
            
            return response.text
        
        except Exception as e:
            return f"Error answering question about image: {str(e)}"
    
    def extract_text_from_image(self, image_path: str) -> str:
        """Extract text from an image (OCR)"""
        try:
            img = Image.open(image_path)
            
            prompt = "Extract all text visible in this image. Return only the text, maintaining the layout as much as possible."
            
            response = self.model.generate_content([prompt, img])
            
            return response.text
        
        except Exception as e:
            return f"Error extracting text from image: {str(e)}"
    
    def compare_images(self, image_path1: str, image_path2: str) -> str:
        """Compare two images"""
        try:
            img1 = Image.open(image_path1)
            img2 = Image.open(image_path2)
            
            prompt = "Compare these two images. What are the similarities and differences?"
            
            response = self.model.generate_content([prompt, img1, img2])
            
            return response.text
        
        except Exception as e:
            return f"Error comparing images: {str(e)}"