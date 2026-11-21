"""
生成高品质多分辨率 Windows 11 托盘/程序图标 captcha.ico
支持分辨率：16x16, 24x24, 32x32, 48x48, 64x64, 128x128, 256x256
"""
import os
from PIL import Image, ImageDraw

def generate_ico(output_path: str):
    # 先在 512x512 高清画布上绘制，再做抗锯齿多重采样缩放到各标准尺寸
    canvas_size = 512
    img = Image.new('RGBA', (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. 外部主圆角矩形（Windows Fluent 蓝）
    margin = 32
    rect_box = [margin, margin, canvas_size - margin, canvas_size - margin]
    radius = 110
    
    # 渐变底色或微明暗对比底色
    primary_color = (0, 120, 212, 255)      # #0078D4
    border_color = (0, 95, 175, 255)
    border_w = 12
    draw.rounded_rectangle(rect_box, radius=radius, fill=primary_color, outline=border_color, width=border_w)

    # 2. 内部白色卡片/短信气泡
    bubble_margin_x = 80
    bubble_top = 115
    bubble_bottom = 350
    bubble_box = [bubble_margin_x, bubble_top, canvas_size - bubble_margin_x, bubble_bottom]
    bubble_radius = 45
    draw.rounded_rectangle(bubble_box, radius=bubble_radius, fill=(255, 255, 255, 255))

    # 气泡尖角（指向左下）
    tail_pts = [
        (130, bubble_bottom - 2),
        (95, bubble_bottom + 50),
        (180, bubble_bottom - 2)
    ]
    draw.polygon(tail_pts, fill=(255, 255, 255, 255))

    # 3. 气泡内的 4 个验证码安全圆点
    dot_y = (bubble_top + bubble_bottom) // 2
    bubble_width = (canvas_size - 2 * bubble_margin_x)
    step = bubble_width / 5
    dot_radius = 18
    dot_color = (0, 120, 212, 255)

    for i in range(1, 5):
        dot_x = int(bubble_margin_x + i * step)
        draw.ellipse([dot_x - dot_radius, dot_y - dot_radius, dot_x + dot_radius, dot_y + dot_radius], fill=dot_color)

    # 4. 底部微弱安全锁标识线条/盾牌提示
    shield_pts = [
        (canvas_size // 2, 400),
        (canvas_size // 2 - 40, 420),
        (canvas_size // 2 - 40, 445),
        (canvas_size // 2, 470),
        (canvas_size // 2 + 40, 445),
        (canvas_size // 2 + 40, 420)
    ]
    draw.polygon(shield_pts, fill=(255, 255, 255, 220))

    # 5. 生成各个尺寸
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    resized_images = [img.resize(s, Image.Resampling.LANCZOS) for s in sizes]

    # 保存为包含所有规格的 ICO 文件
    # 注意：以最大的一张（256x256）作为基准 save，传入 sizes 和 append_images
    largest_img = resized_images[-1]
    largest_img.save(
        output_path,
        format='ICO',
        sizes=sizes,
        append_images=resized_images[:-1]
    )
    print(f"Generated multi-resolution ICO at: {output_path}")

if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    target_ico = os.path.join(script_dir, 'captcha.ico')
    generate_ico(target_ico)
