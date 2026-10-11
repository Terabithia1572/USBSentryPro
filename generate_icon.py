import os
from PIL import Image, ImageDraw

def create_usb_shield_icon(output_path: str):
    sizes = [256, 128, 64, 48, 32, 16]
    images = []

    for size in sizes:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        s = size / 256.0  # scale factor

        # Shield coordinates (normalized to 256)
        # Top-left, top-right, right-bottom curve, tip, left-bottom curve
        shield_pts = [
            (28 * s, 36 * s),
            (128 * s, 18 * s),
            (228 * s, 36 * s),
            (228 * s, 138 * s),
            (128 * s, 238 * s),
            (28 * s, 138 * s),
        ]

        # Outer border / glow
        draw.polygon(shield_pts, fill=(15, 30, 54, 255))
        
        # Inner shield
        inner_pts = [
            (38 * s, 44 * s),
            (128 * s, 28 * s),
            (218 * s, 44 * s),
            (218 * s, 134 * s),
            (128 * s, 226 * s),
            (38 * s, 134 * s),
        ]
        draw.polygon(inner_pts, fill=(24, 48, 89, 255))

        # Cyan Accent Border
        draw.polygon(shield_pts, outline=(0, 168, 255, 255), width=max(1, int(4 * s)))

        # USB Trident (normalized)
        cx = 128 * s
        top_y = 60 * s
        bot_y = 190 * s
        stem_w = max(2, int(8 * s))

        # Main stem
        draw.line([(cx, top_y + 24 * s), (cx, bot_y)], fill=(255, 255, 255, 255), width=stem_w)

        # Center top arrow (triangle)
        arrow_tip = (cx, top_y)
        arrow_l = (cx - 16 * s, top_y + 24 * s)
        arrow_r = (cx + 16 * s, top_y + 24 * s)
        draw.polygon([arrow_tip, arrow_l, arrow_r], fill=(0, 230, 118, 255))

        # Left branch
        lb_y = 105 * s
        draw.line([(cx, lb_y + 30 * s), (cx - 36 * s, lb_y + 10 * s), (cx - 36 * s, lb_y)],
                  fill=(255, 255, 255, 255), width=stem_w)
        # Left circle
        cr = 10 * s
        draw.ellipse([cx - 36 * s - cr, lb_y - cr, cx - 36 * s + cr, lb_y + cr],
                     fill=(255, 179, 0, 255))

        # Right branch
        rb_y = 120 * s
        draw.line([(cx, rb_y + 25 * s), (cx + 36 * s, rb_y + 10 * s), (cx + 36 * s, rb_y)],
                  fill=(255, 255, 255, 255), width=stem_w)
        # Right square
        sr = 9 * s
        draw.rectangle([cx + 36 * s - sr, rb_y - sr, cx + 36 * s + sr, rb_y + sr],
                       fill=(0, 168, 255, 255))

        # Bottom circle on main stem
        br = 12 * s
        draw.ellipse([cx - br, bot_y - br, cx + br, bot_y + br], fill=(255, 255, 255, 255))

        images.append(img)

    # Save as multi-resolution ICO
    images[0].save(output_path, format="ICO", sizes=[(im.width, im.height) for im in images])
    print(f"Generated {output_path} successfully.")

if __name__ == "__main__":
    out = r"C:\Users\Yunus\Desktop\USBSentryPro\app_icon.ico"
    create_usb_shield_icon(out)
