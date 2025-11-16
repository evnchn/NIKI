"""
Photo Processing Module

This module handles photo capture processing for the NIKI Photo Booth.
It decodes base64 image data, crops to overlay aspect ratio, resizes to overlay size,
overlays onto TEMPLATE.png, and saves processed images to disk.
"""

import base64
import os
from io import BytesIO
from time import time

from PIL import Image, ImageOps


def process_and_save_photo(b64url: str, out_dir: str = "user_photos") -> str:
    """
    Process a base64 data URL and save a final image file overlaid on TEMPLATE.png.

    Decodes the base64 image data, crops to overlay aspect ratio, resizes to overlay size,
    overlays onto TEMPLATE.png at specified coordinates, and saves to the specified directory.

    Args:
        b64url: Base64 encoded data URL (data:image/jpeg;base64,... or data:image/png;base64,...)
        out_dir: Output directory for processed images

    Returns:
        str: Relative path to the saved image file

    Raises:
        ValueError: If image data is empty
    """
    if not b64url:
        raise ValueError("Empty image data")

    # Overlay coordinates and size
    overlay_x1 = 100
    overlay_y1 = 102
    overlay_x2 = 1494
    overlay_y2 = 833
    overlay_width = overlay_x2 - overlay_x1
    overlay_height = overlay_y2 - overlay_y1
    aspect = overlay_width / overlay_height

    # Decode base64 data URL
    header, encoded = b64url.split(",", 1)
    if header in ("data:image/jpeg;base64", "data:image/jpg;base64"):
        filetype = "jpg"
    else:
        filetype = "png"

    image_bytes = base64.b64decode(encoded)
    image = Image.open(BytesIO(image_bytes))

    # Correct image orientation based on EXIF data
    ImageOps.exif_transpose(image, in_place=True)

    # Crop to overlay aspect ratio
    width, height = image.size
    if width / height > aspect:
        # Image is too wide, crop sides
        new_width = int(height * aspect)
        left = (width - new_width) // 2
        right = left + new_width
        top = 0
        bottom = height
    else:
        # Image is too tall, crop top/bottom
        new_height = int(width / aspect)
        top = (height - new_height) // 2
        bottom = top + new_height
        left = 0
        right = width

    cropped = image.crop((left, top, right, bottom)).convert("RGB")

    # Resize to overlay size
    target_size = (overlay_width, overlay_height)
    resized = cropped.resize(target_size, Image.LANCZOS)

    # Load TEMPLATE.png
    template_path = "assets/TEMPLATE.png"
    template = Image.open(template_path).convert("RGB")

    # Overlay the resized image onto the template
    template.paste(resized, (overlay_x1, overlay_y1))

    # Ensure output directory exists
    os.makedirs(out_dir, exist_ok=True)

    # Save with timestamp-based filename
    filename = f"{out_dir}/photo_{int(time())}.{filetype}"
    with open(filename, "wb") as f:
        if filetype == "jpg":
            template.save(f, format="JPEG")
        else:
            template.save(f, format="PNG")

    return filename
