import os
from pathlib import Path
from typing import Dict, Optional
from openai import OpenAI
from django.conf import settings

# Audio/video file extensions that need Whisper API
AUDIO_EXTENSIONS = {'.mp3', '.mp4', '.mpeg', '.mpga', '.m4a', '.wav', '.webm'}


def summarize_document(file_path: str, max_length: int = 500, custom_prompt: Optional[str] = None) -> Dict[str, str]:
    """
    Summarize any document by uploading to OpenAI.
    
    Args:
        file_path: Path to file (PDF, DOCX, TXT, audio, video, image)
        max_length: Target summary length in words (default: 500)
        custom_prompt: Optional custom instructions for summarization
        
    Returns:
        {'summary': str, 'file_name': str, 'file_size': str}
    
    Example:
        result = summarize_document("report.pdf") 
        print(result['summary'])
    """
    api_key = getattr(settings, 'OPENAI_API_KEY', os.getenv('OPENAI_API_KEY'))
    client = OpenAI(api_key=api_key)
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    file_size = path.stat().st_size / 1024  # KB
    
    # Route to appropriate API based on file type
    if path.suffix.lower() in AUDIO_EXTENSIONS:
        summary = _process_audio(client, path, max_length, custom_prompt)
    else:
        summary = _process_document(client, path, max_length, custom_prompt)
    
    return {
        "summary": summary,
        "file_name": path.name,
        "file_size": f"{file_size:.2f} KB"
    }


def summarize_text(text: str, max_length: int = 500, custom_prompt: Optional[str] = None) -> Dict[str, str]:
    """
    Summarize plain text without a file.
    
    Args:
        text: Text to summarize
        max_length: Target summary length in words
        custom_prompt: Optional custom instructions
        
    Returns:
        {'summary': str, 'original_length': int, 'summary_length': int}
    """
    api_key = getattr(settings, 'OPENAI_API_KEY', os.getenv('OPENAI_API_KEY'))
    client = OpenAI(api_key=api_key)
    
    prompt = custom_prompt or f"Summarize this in {max_length} words:\n\n{text}"
    
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a concise summarizer."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5
    )
    
    summary = response.choices[0].message.content.strip()
    
    return {
        "summary": summary,
        "original_length": len(text.split()),
        "summary_length": len(summary.split())
    }


# ============================================================================
# Internal Processing Functions
# ============================================================================

def _process_audio(client: OpenAI, path: Path, max_length: int, custom_prompt: Optional[str]) -> str:
    """Process audio/video files using Whisper API."""
    with open(path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
    
    prompt = custom_prompt or f"Summarize this transcript in {max_length} words:\n\n{transcript.text}"
    
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a concise summarizer."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5
    )
    
    return response.choices[0].message.content.strip()


def _process_document(client: OpenAI, path: Path, max_length: int, custom_prompt: Optional[str]) -> str:
    """Process documents using Vision API for images or direct text extraction for docs."""
    
    file_ext = path.suffix.lower()
    
    # For images, use Vision API
    if file_ext in {'.png', '.jpg', '.jpeg', '.gif', '.webp'}:
        import base64
        with open(path, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode('utf-8')
        
        prompt = custom_prompt or f"Describe and summarize this image in {max_length} words."
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/{file_ext[1:]};base64,{image_data}"}
                        }
                    ]
                }
            ]
        )
        return response.choices[0].message.content.strip()
    
    # For PDF and DOCX - extract text first then summarize
    if file_ext == '.pdf':
        try:
            import PyPDF2
            text = ""
            with open(path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text += page.extract_text() + "\n"
        except ImportError:
            return "Error: PyPDF2 not installed. Run: pip install PyPDF2"
    
    elif file_ext == '.docx':
        try:
            from docx import Document
            doc = Document(path)
            text = "\n".join([para.text for para in doc.paragraphs])
        except ImportError:
            return "Error: python-docx not installed. Run: pip install python-docx"
    
    else:
        # Plain text files
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
    
    # Summarize extracted text
    # If text is too long, chunk it
    max_chars = 20000  # Safe limit for GPT-4
    if len(text) > max_chars:
        # Split into chunks and summarize each
        chunks = [text[i:i+max_chars] for i in range(0, len(text), max_chars)]
        summaries = []
        
        for i, chunk in enumerate(chunks):
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a concise summarizer."},
                    {"role": "user", "content": f"Summarize this section:\n\n{chunk}"}
                ],
                temperature=0.5
            )
            summaries.append(response.choices[0].message.content.strip())
        
        # Combine summaries
        combined = "\n\n".join(summaries)
        final_prompt = f"Combine these summaries into one cohesive summary of {max_length} words:\n\n{combined}"
    else:
        final_prompt = custom_prompt or f"Summarize this in {max_length} words:\n\n{text}"
    
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a concise summarizer."},
            {"role": "user", "content": final_prompt}
        ],
        temperature=0.5
    )
    
    return response.choices[0].message.content.strip()
