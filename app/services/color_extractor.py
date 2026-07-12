import io
import logging
from typing import List
import requests
from PIL import Image
from colorthief import ColorThief

logger = logging.getLogger(__name__)

def extract_palette(image_url: str, color_count: int = 5) -> List[str]:
    """
    Downloads an image from a URL and extracts the dominant colors as HEX strings.
    Gracefully falls back to an empty list on any failure.
    """
    if not image_url:
        return []

    try:
        # Download image stream into memory (add timeout to prevent hanging requests)
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()
        
        image_stream = io.BytesIO(response.content)
        
        # DOWN-SCALE THE IMAGE TO PREVENT OUT-OF-MEMORY (OOM) ERRORS ON RENDER (512MB LIMIT)
        # We resize it to a tiny thumbnail (max 400x400). 
        # Dominant colors survive heavy downscaling, and this reduces memory usage by 99%
        with Image.open(image_stream) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.thumbnail((400, 400))
            
            tiny_stream = io.BytesIO()
            img.save(tiny_stream, format='JPEG')
            tiny_stream.seek(0)
        
        # Extract Palette using ColorThief on the optimized tiny stream
        color_thief = ColorThief(tiny_stream)
        
        # get_palette returns a list of RGB tuples: [(26, 26, 26), (255, 255, 255), ...]
        # quality=10 is a good balance between performance and accuracy
        palette = color_thief.get_palette(color_count=color_count, quality=10)
        
        # Convert RGB tuples to HEX codes
        hex_palette = [f"#{r:02x}{g:02x}{b:02x}".upper() for r, g, b in palette]
        
        return hex_palette
        
    except requests.exceptions.RequestException as e:
        logger.warning(f"Failed to download screenshot for color extraction: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error during color extraction: {e}")
        return []
