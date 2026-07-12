import io
import logging
from typing import List
import requests
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
        
        # Extract Palette using ColorThief
        color_thief = ColorThief(image_stream)
        
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
