"""
图标规格处理脚本（京东联盟等平台常用：260×260，jpg/png，≤5MB）

用法（在项目根目录 robot/ 下）:
  .\\.venv\\Scripts\\python.exe .\\src\\test\\test_icon_resize.py
  .\\.venv\\Scripts\\python.exe .\\src\\test\\test_icon_resize.py 路径\\原图.png
  .\\.venv\\Scripts\\python.exe .\\src\\test\\test_icon_resize.py --no-crop-watermark

默认输入（按顺序尝试）:
  1. 命令行传入的图片路径
  2. assets/icon_source.png
  3. assets/ 下最新的 .png / .jpg

输出:
  assets/icon_260x260.png
  assets/icon_260x260.jpg
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from PIL import Image
except ImportError:
    print('请先安装 Pillow: .\\.venv\\Scripts\\pip.exe install Pillow')
    raise

TARGET_SIZE = 260
MAX_BYTES = 5 * 1024 * 1024
ASSETS = _ROOT / 'assets'
DEFAULT_OUTPUT_PNG = ASSETS / 'icon_260x260.png'
DEFAULT_OUTPUT_JPG = ASSETS / 'icon_260x260.jpg'

def _cursor_assets_dir() -> Path:
    return Path.home() / '.cursor' / 'projects' / (
        'c-Users-ICN00069-PycharmProjects-ReleasePlanCheck-robot'
    ) / 'assets'


def _cursor_saved_icon() -> Path | None:
    assets = _cursor_assets_dir()
    if not assets.is_dir():
        return None
    exact = assets / (
        'c__Users_ICN00069_AppData_Roaming_Cursor_User_workspaceStorage_'
        'af108051d01eae41b551edc0671b41bb_images_________2_-'
        'c3e7dad3-3720-494e-8fa0-ce3e76e7cfa9.png'
    )
    if exact.is_file():
        return exact
    pngs = sorted(assets.glob('*.png'), key=lambda p: p.stat().st_mtime, reverse=True)
    return pngs[0] if pngs else None


def _find_default_input() -> Path | None:
    fixed = ASSETS / 'icon_source.png'
    if fixed.is_file():
        return fixed
    cursor_icon = _cursor_saved_icon()
    if cursor_icon:
        return cursor_icon
    if not ASSETS.is_dir():
        return None
    candidates = []
    for ext in ('*.png', '*.jpg', '*.jpeg', '*.webp'):
        candidates.extend(ASSETS.glob(ext))
    skip = {DEFAULT_OUTPUT_PNG.name, DEFAULT_OUTPUT_JPG.name, 'rebate_bot_icon.png'}
    candidates = [p for p in candidates if p.name not in skip]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _center_square_crop(img: Image.Image) -> Image.Image:
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    return img.crop((left, top, left + side, top + side))


def _trim_watermark_band(img: Image.Image, ratio: float = 0.06) -> Image.Image:
    """裁掉底部一条（常见 AI 水印在右下角）"""
    w, h = img.size
    cut = max(1, int(h * ratio))
    return img.crop((0, 0, w, h - cut))


def process_icon(
    src: Path,
    out_png: Path = DEFAULT_OUTPUT_PNG,
    out_jpg: Path = DEFAULT_OUTPUT_JPG,
    crop_watermark: bool = True,
    jpg_quality: int = 92,
) -> dict:
    if not src.is_file():
        raise FileNotFoundError(f'找不到原图: {src}')

    out_png.parent.mkdir(parents=True, exist_ok=True)

    img = Image.open(src)
    img.load()
    if img.mode not in ('RGB', 'RGBA'):
        img = img.convert('RGBA')

    if crop_watermark:
        img = _trim_watermark_band(img)

    img = _center_square_crop(img)
    img = img.resize((TARGET_SIZE, TARGET_SIZE), Image.Resampling.LANCZOS)

    # PNG（保留透明或原背景）
    if img.mode == 'RGBA':
        img.save(out_png, 'PNG', optimize=True)
    else:
        img.convert('RGB').save(out_png, 'PNG', optimize=True)

    # JPG（黑底图用黑色铺底，避免透明变杂色）
    if img.mode == 'RGBA':
        bg = Image.new('RGB', (TARGET_SIZE, TARGET_SIZE), (0, 0, 0))
        bg.paste(img, mask=img.split()[3])
        rgb = bg
    else:
        rgb = img.convert('RGB')
    rgb.save(out_jpg, 'JPEG', quality=jpg_quality, optimize=True)

    report = {
        'source': str(src.resolve()),
        'source_size': src.stat().st_size,
        'source_dimensions': Image.open(src).size,
        'outputs': [],
    }
    for path in (out_png, out_jpg):
        with Image.open(path) as out:
            w, h = out.size
        nbytes = path.stat().st_size
        ok_dim = w == TARGET_SIZE and h == TARGET_SIZE
        ok_size = nbytes <= MAX_BYTES
        report['outputs'].append({
            'path': str(path.resolve()),
            'format': path.suffix.lower().lstrip('.'),
            'dimensions': f'{w}x{h}',
            'bytes': nbytes,
            'ok_dimensions': ok_dim,
            'ok_size': ok_size,
            'ok': ok_dim and ok_size and path.suffix.lower() in ('.png', '.jpg', '.jpeg'),
        })
    return report


def _print_report(report: dict) -> bool:
    print('=' * 60)
    print('图标处理报告')
    print('=' * 60)
    print(f"原图: {report['source']}")
    print(f"原图尺寸: {report['source_dimensions'][0]}x{report['source_dimensions'][1]}")
    print(f"原图大小: {report['source_size']:,} 字节")
    print()
    all_ok = True
    for item in report['outputs']:
        status = '通过' if item['ok'] else '未通过'
        print(f"[{status}] {item['path']}")
        print(f"       格式 {item['format']} | {item['dimensions']} | {item['bytes']:,} 字节")
        if not item['ok_dimensions']:
            print(f'       要求尺寸 {TARGET_SIZE}x{TARGET_SIZE}')
        if not item['ok_size']:
            print(f'       要求 ≤ {MAX_BYTES:,} 字节 (5MB)')
        all_ok = all_ok and item['ok']
    print('=' * 60)
    if all_ok:
        print('全部符合：260×260，jpg/png，5MB 以内')
    else:
        print('存在不符合项，请检查输出')
    return all_ok


def main() -> int:
    parser = argparse.ArgumentParser(description='生成 260×260 联盟图标（png/jpg）')
    parser.add_argument('input', nargs='?', help='原图路径（可选）')
    parser.add_argument(
        '--no-crop-watermark',
        action='store_true',
        help='不裁切底部水印区域',
    )
    parser.add_argument('--png', default=str(DEFAULT_OUTPUT_PNG), help='输出 PNG 路径')
    parser.add_argument('--jpg', default=str(DEFAULT_OUTPUT_JPG), help='输出 JPG 路径')
    args = parser.parse_args()

    if args.input:
        src = Path(args.input)
        if not src.is_absolute():
            src = (_ROOT / src).resolve()
    else:
        src = _find_default_input()
        if not src:
            print('未找到原图。请任选其一：')
            print(f'  1. 将图片放到 {ASSETS / "icon_source.png"}')
            print('  2. 命令行传入: python src/test/test_icon_resize.py 你的图.png')
            return 1

    print(f'使用原图: {src}\n')
    report = process_icon(
        src,
        out_png=Path(args.png),
        out_jpg=Path(args.jpg),
        crop_watermark=not args.no_crop_watermark,
    )
    return 0 if _print_report(report) else 1


if __name__ == '__main__':
    raise SystemExit(main())
