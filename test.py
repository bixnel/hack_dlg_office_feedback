from PIL import Image, ImageDraw

img = Image.new('RGBA', (180, 210), (255, 0, 0, 0))
draw = ImageDraw.Draw(img)
x = 90
y = 120
r = 85
r2 = 55
draw.ellipse((x-r, y-r, x+r, y+r), fill=(89, 109, 131, 255))
draw.ellipse((x-r2, y-r2, x+r2, y+r2), fill=(255, 0, 0, 0))
draw.arc((x-r, y-r, x+r, y+r), 270, 360, width=30, fill=(255, 0, 0, 255))
img.save('pil_red.png')
