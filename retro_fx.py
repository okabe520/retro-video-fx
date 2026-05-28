#!/usr/bin/env python3
"""
复古视频效果处理器 — 噪点 + 像素化 + 高对比度 + 扫描线 + 晕影
"""

import argparse
import random
import sys
from pathlib import Path

import cv2
import numpy as np


def add_noise(frame: np.ndarray, intensity: float = 0.05) -> np.ndarray:
    """叠加随机胶片颗粒噪点."""
    noise = np.random.normal(0, 255 * intensity, frame.shape).astype(np.int16)
    noisy = frame.astype(np.int16) + noise
    return np.clip(noisy, 0, 255).astype(np.uint8)


def add_chromatic_noise(frame: np.ndarray, intensity: float = 0.04) -> np.ndarray:
    """RGB 通道独立噪点，模拟老胶片色彩偏移."""
    result = frame.copy()
    for c in range(3):
        channel_noise = np.random.normal(0, 255 * intensity, frame.shape[:2])
        channel = result[:, :, c].astype(np.int16) + channel_noise.astype(np.int16)
        result[:, :, c] = np.clip(channel, 0, 255).astype(np.uint8)
    return result


def pixelate(frame: np.ndarray, pixel_size: int = 4) -> np.ndarray:
    """像素化 — 缩小再放大实现块状效果."""
    h, w = frame.shape[:2]
    small = cv2.resize(frame, (max(1, w // pixel_size), max(1, h // pixel_size)),
                       interpolation=cv2.INTER_LINEAR)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)


def boost_contrast(frame: np.ndarray, factor: float = 1.8, midpoint: int = 127) -> np.ndarray:
    """高对比度 — 以 mid 为中心拉伸像素值."""
    if factor <= 0:
        return frame
    stretched = (frame.astype(np.float32) - midpoint) * factor + midpoint
    return np.clip(stretched, 0, 255).astype(np.uint8)


def add_scanlines(frame: np.ndarray, spacing: int = 4, alpha: float = 0.15) -> np.ndarray:
    """CRT 扫描线效果."""
    h = frame.shape[0]
    mask = np.ones((h, 1), dtype=np.float32)
    for y in range(1, h, spacing):
        mask[y] = 1.0 - alpha
    return (frame.astype(np.float32) * mask[:, :, np.newaxis]).clip(0, 255).astype(np.uint8)


def add_vignette(frame: np.ndarray, strength: float = 0.5) -> np.ndarray:
    """边缘暗角效果."""
    h, w = frame.shape[:2]
    xs = np.linspace(-1, 1, w)
    ys = np.linspace(-1, 1, h)
    xv, yv = np.meshgrid(xs, ys)
    dist = np.sqrt(xv ** 2 + yv ** 2)
    mask = 1.0 - np.clip(dist * strength, 0, 1)
    return (frame.astype(np.float32) * mask[:, :, np.newaxis]).clip(0, 255).astype(np.uint8)


def add_color_shift(frame: np.ndarray, shift_r: int = 2, shift_b: int = -2) -> np.ndarray:
    """轻微色差偏移 — 模拟老镜头色散."""
    h, w = frame.shape[:2]
    B, G, R = cv2.split(frame)

    M = np.float32([[1, 0, shift_r], [0, 1, 0]])
    R_shifted = cv2.warpAffine(R, M, (w, h))

    M = np.float32([[1, 0, shift_b], [0, 1, 0]])
    B_shifted = cv2.warpAffine(B, M, (w, h))

    return cv2.merge([B_shifted, G, R_shifted])


def apply_flicker(frame: np.ndarray, strength: float = 0.05) -> np.ndarray:
    """随机亮度闪烁 — 模拟老放映机."""
    flicker = 1.0 + random.uniform(-strength, strength)
    result = (frame.astype(np.float32) * flicker).clip(0, 255)
    return result.astype(np.uint8)


def process_video(
    input_path: str,
    output_path: str,
    *,
    noise: float = 0.04,
    chromatic_noise: float = 0.02,
    pixel_size: int = 4,
    contrast: float = 1.6,
    scanlines: bool = True,
    scanline_alpha: float = 0.15,
    vignette: bool = True,
    vignette_strength: float = 0.45,
    flicker: bool = True,
    flicker_strength: float = 0.04,
    color_shift: bool = True,
    scale: float = 1.0,
    start_sec: float = 0.0,
    duration_sec: float | None = None,
    fps: float | None = None,
    show_preview: bool = False,
) -> None:
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        print(f"错误: 无法打开文件 {input_path}")
        sys.exit(1)

    src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    src_fps = cap.get(cv2.CAP_PROP_FPS)
    out_fps = fps or src_fps

    start_frame = int(start_sec * src_fps)
    if duration_sec is not None:
        end_frame = start_frame + int(duration_sec * src_fps)
    else:
        end_frame = total

    work_w = max(1, int(src_w * scale))
    work_h = max(1, int(src_h * scale))

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_path, fourcc, out_fps, (src_w, src_h))

    seg_frames = end_frame - start_frame
    print(f"原始: {src_w}x{src_h}  工作分辨率: {work_w}x{work_h}  FPS: {out_fps:.0f}  总帧数: {total}")
    if start_sec > 0 or duration_sec is not None:
        print(f"截取: {start_sec:.1f}s ~ {end_frame / src_fps:.1f}s ({seg_frames}帧)")
    print(f"效果: 噪点={noise}/{chromatic_noise} 像素={pixel_size}px 对比度=x{contrast}", end="")
    if scale < 1.0:
        print(f" 缩放=x{scale:.0%}", end="")
    if scanlines:
        print(" 扫描线", end="")
    if vignette:
        print(" 晕影", end="")
    if flicker:
        print(" 闪烁", end="")
    if color_shift:
        print(" 色散", end="")
    print()

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    frame_idx = start_frame
    while frame_idx < end_frame:
        ret, frame = cap.read()
        if not ret:
            break

        if scale < 1.0:
            frame = cv2.resize(frame, (work_w, work_h), interpolation=cv2.INTER_LINEAR)

        # ---- 效果链 ----
        processed = pixelate(frame, pixel_size)
        processed = add_noise(processed, noise)
        processed = add_chromatic_noise(processed, chromatic_noise)
        processed = boost_contrast(processed, contrast)

        if color_shift:
            processed = add_color_shift(processed)

        if scanlines:
            processed = add_scanlines(processed, alpha=scanline_alpha)

        if vignette:
            processed = add_vignette(processed, vignette_strength)

        if flicker:
            processed = apply_flicker(processed, flicker_strength)

        if scale < 1.0:
            processed = cv2.resize(processed, (src_w, src_h), interpolation=cv2.INTER_NEAREST)

        writer.write(processed)

        if show_preview:
            cv2.imshow("retro (q=退出)", processed)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        frame_idx += 1
        done = frame_idx - start_frame
        pct = done * 100 // seg_frames if seg_frames else 0
        if frame_idx % 5 == 0 or frame_idx == end_frame:
            print(f"\r处理进度: {done}/{seg_frames} ({pct}%)", end="", flush=True)

    print()
    cap.release()
    writer.release()
    if show_preview:
        cv2.destroyAllWindows()
    print(f"完成 → {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="复古视频效果处理器 — 噪点/像素化/高对比度/扫描线/晕影",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python retro_fx.py input.mp4 -o output.mp4 --preset vhs --scale 0.25 -t 5
  python retro_fx.py input.mp4 -o output.mp4 --preset horror --scale 0.3
  python retro_fx.py input.mp4 -o out.mp4 --noise 0.08 --pixel 8 --contrast 2.0
  python retro_fx.py input.mp4 -o out.mp4 --start 30 -t 10 --scale 0.25 --preview
        """,
    )

    parser.add_argument("input", help="输入视频路径")
    parser.add_argument("-o", "--output", default="retro_output.mp4", help="输出路径 (默认: retro_output.mp4)")
    parser.add_argument("--noise", type=float, default=0.04, help="亮度噪点强度 (0-1, 默认 0.04)")
    parser.add_argument("--chroma-noise", type=float, default=0.02, help="色彩噪点强度 (0-1, 默认 0.02)")
    parser.add_argument("--pixel", type=int, default=4, help="像素块大小 (默认 4)")
    parser.add_argument("--contrast", type=float, default=1.6, help="对比度倍数 (默认 1.6)")
    parser.add_argument("--no-scanlines", action="store_true", help="关闭扫描线")
    parser.add_argument("--scanline-alpha", type=float, default=0.15, help="扫描线强度 (默认 0.15)")
    parser.add_argument("--no-vignette", action="store_true", help="关闭晕影")
    parser.add_argument("--vignette-strength", type=float, default=0.45, help="晕影强度 (默认 0.45)")
    parser.add_argument("--no-flicker", action="store_true", help="关闭闪烁")
    parser.add_argument("--flicker-strength", type=float, default=0.04, help="闪烁强度 (默认 0.04)")
    parser.add_argument("--no-color-shift", action="store_true", help="关闭色差")
    parser.add_argument("--scale", type=float, default=1.0, help="处理缩放比例 0.1-1.0 (默认 1.0，越小越快越复古)")
    parser.add_argument("--start", type=float, default=0.0, help="起始时间(秒) (默认从头开始)")
    parser.add_argument("-t", "--duration", type=float, default=None, help="截取时长(秒) (默认全部)")
    parser.add_argument("--preview", action="store_true", help="处理时实时预览")
    parser.add_argument("--preset", choices=["80s", "90s", "arcade", "horror", "vhs"], help="预设风格")

    args = parser.parse_args()

    # 预设风格
    presets = {
        "80s":    dict(noise=0.06, chromatic_noise=0.04, pixel_size=5, contrast=1.8,
                        scanlines=True, scanline_alpha=0.20, vignette=True, vignette_strength=0.55,
                        flicker=True, flicker_strength=0.06, color_shift=True),
        "90s":    dict(noise=0.03, chromatic_noise=0.01, pixel_size=3, contrast=1.4,
                        scanlines=False, vignette=True, vignette_strength=0.35,
                        flicker=False, color_shift=False),
        "arcade":  dict(noise=0.02, chromatic_noise=0.01, pixel_size=8, contrast=2.0,
                        scanlines=True, scanline_alpha=0.12, vignette=False,
                        flicker=False, color_shift=False),
        "horror":  dict(noise=0.10, chromatic_noise=0.06, pixel_size=3, contrast=2.2,
                        scanlines=True, scanline_alpha=0.25, vignette=True, vignette_strength=0.70,
                        flicker=True, flicker_strength=0.10, color_shift=True),
        "vhs":     dict(noise=0.05, chromatic_noise=0.05, pixel_size=2, contrast=1.5,
                        scanlines=True, scanline_alpha=0.18, vignette=True, vignette_strength=0.40,
                        flicker=True, flicker_strength=0.03, color_shift=True),
    }

    kwargs: dict = dict(
        noise=args.noise,
        chromatic_noise=args.chroma_noise,
        pixel_size=args.pixel,
        contrast=args.contrast,
        scanlines=not args.no_scanlines,
        scanline_alpha=args.scanline_alpha,
        vignette=not args.no_vignette,
        vignette_strength=args.vignette_strength,
        flicker=not args.no_flicker,
        flicker_strength=args.flicker_strength,
        color_shift=not args.no_color_shift,
        scale=args.scale,
        start_sec=args.start,
        duration_sec=args.duration,
    )

    if args.preset:
        kwargs.update(presets[args.preset])
        print(f"预设: {args.preset}")

    process_video(args.input, args.output, **kwargs, show_preview=args.preview)


if __name__ == "__main__":
    main()
