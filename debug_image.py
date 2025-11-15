from PIL import Image, ImageOps

# Load the image
image = Image.open("debug_photo_1763222297.raw.jpg")

# Apply exif_transpose
ImageOps.exif_transpose(image, in_place=True)

# Save as DEBUG.png
image.save("DEBUG.png")
