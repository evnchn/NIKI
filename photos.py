"""Photo processing helpers for saving and preparing images.

This encapsulates decoding base64 data URLs, cropping to the project's
preferred aspect ratio, resizing, adding borders, and saving to disk.
"""

import base64
import os
from io import BytesIO
from time import time

from PIL import Image


def process_and_save_photo(b64url: str, out_dir: str = 'user_photos') -> str:
    """Process a base64 data URL and save a final image file in `out_dir`.

    Returns the filename (relative path) where the image was saved.
    """
    if not b64url:
        raise ValueError('Empty image data')
    header, encoded = b64url.split(',', 1)
    if header in ('data:image/jpeg;base64', 'data:image/jpg;base64'):
        filetype = 'jpg'
    else:
        filetype = 'png'
    image_bytes = base64.b64decode(encoded)
    image = Image.open(BytesIO(image_bytes))

    # Crop to 14:9 aspect ratio (horizontal)
    width, height = image.size
    aspect = 14 / 9
    if width / height > aspect:
        new_width = int(height * aspect)
        left = (width - new_width) // 2
        right = left + new_width
        top = 0
        bottom = height
    else:
        new_height = int(width / aspect)
        top = (height - new_height) // 2
        bottom = top + new_height
        left = 0
        right = width

    cropped = image.crop((left, top, right, bottom)).convert('RGB')

    # Resize to inner area 1400x900 then add 50px white border
    target_size = (1400, 900)
    resized = cropped.resize(target_size, Image.LANCZOS)
    border_px = 50
    bordered_width = resized.width + border_px * 2
    bordered_height = resized.height + border_px * 2
    bordered = Image.new('RGB', (bordered_width, bordered_height), (255, 255, 255))
    bordered.paste(resized, (border_px, border_px))

    os.makedirs(out_dir, exist_ok=True)
    filename = f'{out_dir}/photo_{int(time())}.{filetype}'
    with open(filename, 'wb') as f:
        if filetype == 'jpg':
            bordered.save(f, format='JPEG')
        else:
            bordered.save(f, format='PNG')
    return filename
