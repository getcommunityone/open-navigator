import os
from PIL import Image

public_dir = r"c:\Users\viloh\Documents\Vilohit's Programs\volunteer\communityone-navigator\open-navigator\web_app\public"
source_image = os.path.join(public_dir, "communityone_logo.jpg")

sizes = [192, 512]
with Image.open(source_image) as img:
    # Use LANCZOS for high-quality downsampling/upsampling
    for size in sizes:
        resized = img.resize((size, size), Image.Resampling.LANCZOS)
        # Save as PNG
        out_path = os.path.join(public_dir, f"communityone_logo_{size}.png")
        resized.save(out_path, format="PNG")
        print(f"Created {out_path}")
