#!/usr/bin/env python3
"""复古视频效果处理器 — GUI"""

import random
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

import cv2
import numpy as np


# ═══════════════════ 效果函数 (同 CLI) ═══════════════════

def add_noise(frame, intensity=0.05):
    noise = np.random.normal(0, 255 * intensity, frame.shape).astype(np.int16)
    return np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)

def add_chromatic_noise(frame, intensity=0.04):
    result = frame.copy()
    for c in range(3):
        cn = np.random.normal(0, 255 * intensity, frame.shape[:2])
        ch = result[:, :, c].astype(np.int16) + cn.astype(np.int16)
        result[:, :, c] = np.clip(ch, 0, 255).astype(np.uint8)
    return result

def pixelate(frame, pixel_size=4):
    h, w = frame.shape[:2]
    small = cv2.resize(frame, (max(1, w // pixel_size), max(1, h // pixel_size)), interpolation=cv2.INTER_LINEAR)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)

def boost_contrast(frame, factor=1.8, midpoint=127):
    if factor <= 0:
        return frame
    return np.clip((frame.astype(np.float32) - midpoint) * factor + midpoint, 0, 255).astype(np.uint8)

def add_scanlines(frame, alpha=0.15):
    h = frame.shape[0]
    mask = np.ones((h, 1), dtype=np.float32)
    for y in range(1, h, 4):
        mask[y] = 1.0 - alpha
    return (frame.astype(np.float32) * mask[:, :, np.newaxis]).clip(0, 255).astype(np.uint8)

def add_vignette(frame, strength=0.5):
    h, w = frame.shape[:2]
    xs, ys = np.linspace(-1, 1, w), np.linspace(-1, 1, h)
    xv, yv = np.meshgrid(xs, ys)
    mask = 1.0 - np.clip(np.sqrt(xv**2 + yv**2) * strength, 0, 1)
    return (frame.astype(np.float32) * mask[:, :, np.newaxis]).clip(0, 255).astype(np.uint8)

def add_color_shift(frame, shift_r=2, shift_b=-2):
    h, w = frame.shape[:2]
    B, G, R = cv2.split(frame)
    R2 = cv2.warpAffine(R, np.float32([[1, 0, shift_r], [0, 1, 0]]), (w, h))
    B2 = cv2.warpAffine(B, np.float32([[1, 0, shift_b], [0, 1, 0]]), (w, h))
    return cv2.merge([B2, G, R2])

def apply_flicker(frame, strength=0.05):
    f = 1.0 + random.uniform(-strength, strength)
    return np.clip(frame.astype(np.float32) * f, 0, 255).astype(np.uint8)


# ═══════════════════ 预设 ═══════════════════

PRESETS = {
    "vhs":     dict(noise=0.05, chroma=0.05, pixel=2, contrast=1.5, scanlines=True, scan_alpha=0.18, vignette=True, vig_str=0.40, flicker=True, flk_str=0.03, color_shift=True),
    "80s":     dict(noise=0.06, chroma=0.04, pixel=5, contrast=1.8, scanlines=True, scan_alpha=0.20, vignette=True, vig_str=0.55, flicker=True, flk_str=0.06, color_shift=True),
    "90s":     dict(noise=0.03, chroma=0.01, pixel=3, contrast=1.4, scanlines=False, vignette=True, vig_str=0.35, flicker=False, color_shift=False),
    "arcade":   dict(noise=0.02, chroma=0.01, pixel=8, contrast=2.0, scanlines=True, scan_alpha=0.12, vignette=False, flicker=False, color_shift=False),
    "horror":   dict(noise=0.10, chroma=0.06, pixel=3, contrast=2.2, scanlines=True, scan_alpha=0.25, vignette=True, vig_str=0.70, flicker=True, flk_str=0.10, color_shift=True),
    "custom":   {},
}


# ═══════════════════ 主窗口 ═══════════════════

class RetroApp:
    def __init__(self, root):
        self.root = root
        self.root.title("复古视频效果处理器")
        self.root.geometry("680x620")
        self.root.resizable(False, False)
        self.running = False

        style = ttk.Style()
        style.theme_use("clam")

        self._build_ui()

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)

        # ── 文件选择 ──
        file_frame = ttk.LabelFrame(main, text="文件", padding=8)
        file_frame.pack(fill="x", pady=(0, 8))

        ttk.Label(file_frame, text="输入视频:").grid(row=0, column=0, sticky="w")
        self.input_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.input_var, width=60).grid(row=0, column=1, padx=6)
        ttk.Button(file_frame, text="浏览...", command=self._pick_input, width=8).grid(row=0, column=2)

        ttk.Label(file_frame, text="输出路径:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.output_var = tk.StringVar(value=str(Path.home() / "retro_output.mp4"))
        ttk.Entry(file_frame, textvariable=self.output_var, width=60).grid(row=1, column=1, padx=6, pady=(8, 0))
        ttk.Button(file_frame, text="浏览...", command=self._pick_output, width=8).grid(row=1, column=2, pady=(8, 0))

        # ── 时间截取 ──
        time_frame = ttk.LabelFrame(main, text="时间截取", padding=8)
        time_frame.pack(fill="x", pady=(0, 8))

        ttk.Label(time_frame, text="起始 (秒):").grid(row=0, column=0, sticky="w")
        self.start_var = tk.StringVar(value="0")
        ttk.Entry(time_frame, textvariable=self.start_var, width=8).grid(row=0, column=1, padx=4)

        ttk.Label(time_frame, text="结束 (秒, 空=到结尾):").grid(row=0, column=2, sticky="w", padx=(16, 0))
        self.end_var = tk.StringVar(value="")
        ttk.Entry(time_frame, textvariable=self.end_var, width=8).grid(row=0, column=3, padx=4)

        ttk.Label(time_frame, text="缩放 (0.1-1.0):").grid(row=0, column=4, sticky="w", padx=(16, 0))
        self.scale_var = tk.DoubleVar(value=0.3)
        ttk.Scale(time_frame, from_=0.1, to=1.0, variable=self.scale_var, length=120).grid(row=0, column=5, padx=4)
        ttk.Label(time_frame, textvariable=tk.StringVar(value=""), width=4).grid(row=0, column=6)
        # scale label needs to track the variable
        self.scale_pct = ttk.Label(time_frame, text="30%", width=4)
        self.scale_pct.grid(row=0, column=6)
        self.scale_var.trace_add("write", lambda *_: self.scale_pct.configure(text=f"{self.scale_var.get():.0%}"))

        # ── 预设 ──
        preset_frame = ttk.LabelFrame(main, text="预设风格", padding=8)
        preset_frame.pack(fill="x", pady=(0, 8))

        self.preset_var = tk.StringVar(value="vhs")
        preset_row = ttk.Frame(preset_frame)
        preset_row.pack(fill="x")
        for i, (name, _) in enumerate(PRESETS.items()):
            ttk.Radiobutton(preset_row, text=name.upper(), value=name, variable=self.preset_var, command=self._apply_preset).pack(side="left", padx=6)

        # ── 效果参数 ──
        fx_frame = ttk.LabelFrame(main, text="效果参数", padding=8)
        fx_frame.pack(fill="x", pady=(0, 8))

        self.vars = {}

        row = ttk.Frame(fx_frame)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="亮度噪点:", width=10).pack(side="left")
        self.vars["noise"] = tk.DoubleVar(value=0.05)
        ttk.Scale(row, from_=0.0, to=0.20, variable=self.vars["noise"], length=130).pack(side="left")
        ttk.Label(row, text="0.05", width=5).pack(side="left")
        self.vars["noise"].trace_add("write", lambda *_: self._on_param_change())

        ttk.Label(row, text="  像素块:", width=8).pack(side="left", padx=(12, 0))
        self.vars["pixel"] = tk.IntVar(value=2)
        ttk.Scale(row, from_=1, to=16, variable=self.vars["pixel"], length=130).pack(side="left")
        ttk.Label(row, text="2", width=5).pack(side="left")
        self.vars["pixel"].trace_add("write", lambda *_: self._on_param_change())

        row2 = ttk.Frame(fx_frame)
        row2.pack(fill="x", pady=2)
        ttk.Label(row2, text="色彩噪点:", width=10).pack(side="left")
        self.vars["chroma"] = tk.DoubleVar(value=0.05)
        ttk.Scale(row2, from_=0.0, to=0.15, variable=self.vars["chroma"], length=130).pack(side="left")
        ttk.Label(row2, text="0.05", width=5).pack(side="left")
        self.vars["chroma"].trace_add("write", lambda *_: self._on_param_change())

        ttk.Label(row2, text="  对比度:", width=8).pack(side="left", padx=(12, 0))
        self.vars["contrast"] = tk.DoubleVar(value=1.5)
        ttk.Scale(row2, from_=1.0, to=3.0, variable=self.vars["contrast"], length=130).pack(side="left")
        ttk.Label(row2, text="1.5", width=5).pack(side="left")
        self.vars["contrast"].trace_add("write", lambda *_: self._on_param_change())

        # 开关行
        toggle_row = ttk.Frame(fx_frame)
        toggle_row.pack(fill="x", pady=4)
        self.vars["scanlines"] = tk.BooleanVar(value=True)
        ttk.Checkbutton(toggle_row, text="扫描线", variable=self.vars["scanlines"], command=self._on_param_change).pack(side="left", padx=4)
        self.vars["vignette"] = tk.BooleanVar(value=True)
        ttk.Checkbutton(toggle_row, text="晕影", variable=self.vars["vignette"], command=self._on_param_change).pack(side="left", padx=4)
        self.vars["flicker"] = tk.BooleanVar(value=True)
        ttk.Checkbutton(toggle_row, text="闪烁", variable=self.vars["flicker"], command=self._on_param_change).pack(side="left", padx=4)
        self.vars["color_shift"] = tk.BooleanVar(value=True)
        ttk.Checkbutton(toggle_row, text="色差", variable=self.vars["color_shift"], command=self._on_param_change).pack(side="left", padx=4)

        # ── 进度 ──
        prog_frame = ttk.LabelFrame(main, text="进度", padding=8)
        prog_frame.pack(fill="x", pady=(0, 8))

        self.progress = ttk.Progressbar(prog_frame, length=400, mode="determinate")
        self.progress.pack(fill="x")
        self.progress_label = ttk.Label(prog_frame, text="就绪")
        self.progress_label.pack(anchor="w", pady=(2, 0))

        # ── 按钮 ──
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill="x")

        self.run_btn = ttk.Button(btn_frame, text="开始转换", command=self._start)
        self.run_btn.pack(side="left", padx=4)

        self.cancel_btn = ttk.Button(btn_frame, text="取消", command=self._cancel, state="disabled")
        self.cancel_btn.pack(side="left", padx=4)

    # ═══════════════ 交互 ═══════════════

    def _pick_input(self):
        path = filedialog.askopenfilename(
            title="选择输入视频",
            filetypes=[("视频文件", "*.mp4 *.avi *.mov *.mkv *.wmv *.webm"), ("全部文件", "*.*")],
        )
        if path:
            self.input_var.set(path)
            # 自动生成输出路径
            in_path = Path(path)
            out = in_path.parent / f"{in_path.stem}_retro.mp4"
            self.output_var.set(str(out))

    def _pick_output(self):
        path = filedialog.asksaveasfilename(
            title="保存输出视频",
            defaultextension=".mp4",
            filetypes=[("MP4 视频", "*.mp4"), ("全部文件", "*.*")],
        )
        if path:
            self.output_var.set(path)

    def _on_param_change(self):
        if self.preset_var.get() != "custom":
            self.preset_var.set("custom")

    def _apply_preset(self):
        name = self.preset_var.get()
        cfg = PRESETS.get(name)
        if not cfg or not cfg:
            return
        for k, v in cfg.items():
            if k in self.vars:
                self.vars[k].set(v)
            elif k == "scan_alpha" or k == "vig_str" or k == "flk_str":
                pass  # simplified params covered above

    def _start(self):
        if self.running:
            return
        if not self.input_var.get():
            messagebox.showwarning("提示", "请先选择输入视频文件")
            return
        if not Path(self.input_var.get()).exists():
            messagebox.showerror("错误", f"文件不存在:\n{self.input_var.get()}")
            return

        self.running = True
        self.run_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.progress["value"] = 0
        self.progress_label.configure(text="处理中...")

        threading.Thread(target=self._process, daemon=True).start()

    def _cancel(self):
        self.running = False
        self.progress_label.configure(text="已取消")

    # ═══════════════ 处理 ═══════════════

    def _process(self):
        try:
            in_path = self.input_var.get()
            out_path = self.output_var.get()
            scale = self.scale_var.get()

            start_val = self.start_var.get().strip()
            end_val = self.end_var.get().strip()
            start_sec = float(start_val) if start_val else 0.0
            end_sec = float(end_val) if end_val else None

            cap = cv2.VideoCapture(in_path)
            if not cap.isOpened():
                self._done(f"错误: 无法打开 {in_path}")
                return

            src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)

            start_frame = int(start_sec * fps)
            if end_sec is not None:
                end_frame = int(end_sec * fps)
            else:
                end_frame = total_frames

            work_w = max(1, int(src_w * scale))
            work_h = max(1, int(src_h * scale))

            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(out_path, fourcc, fps, (src_w, src_h))

            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

            # 读取参数
            noise_val = self.vars["noise"].get()
            chroma_val = self.vars["chroma"].get()
            pixel_val = self.vars["pixel"].get()
            contrast_val = self.vars["contrast"].get()
            do_scan = self.vars["scanlines"].get()
            do_vig = self.vars["vignette"].get()
            do_flk = self.vars["flicker"].get()
            do_cs = self.vars["color_shift"].get()

            seg_frames = end_frame - start_frame
            frame_idx = start_frame

            while frame_idx < end_frame and self.running:
                ret, frame = cap.read()
                if not ret:
                    break

                if scale < 1.0:
                    frame = cv2.resize(frame, (work_w, work_h), interpolation=cv2.INTER_LINEAR)

                frame = pixelate(frame, pixel_val)
                frame = add_noise(frame, noise_val)
                frame = add_chromatic_noise(frame, chroma_val)
                frame = boost_contrast(frame, contrast_val)

                if do_cs:
                    frame = add_color_shift(frame)
                if do_scan:
                    frame = add_scanlines(frame)
                if do_vig:
                    frame = add_vignette(frame)
                if do_flk:
                    frame = apply_flicker(frame)

                if scale < 1.0:
                    frame = cv2.resize(frame, (src_w, src_h), interpolation=cv2.INTER_NEAREST)

                writer.write(frame)
                frame_idx += 1

                # 更新进度 (每5帧)
                if frame_idx % 5 == 0:
                    done = frame_idx - start_frame
                    pct = int(done / seg_frames * 100) if seg_frames else 0
                    self.root.after(0, self._update_progress, pct, done, seg_frames)

            cap.release()
            writer.release()

            if self.running:
                self._done(f"完成 → {out_path}")
            else:
                self._done("已取消")

        except Exception as e:
            self._done(f"错误: {e}")

    def _update_progress(self, pct, done, total):
        self.progress["value"] = pct
        self.progress_label.configure(text=f"{done}/{total} ({pct}%)")

    def _done(self, msg):
        self.root.after(0, lambda: self._done_ui(msg))

    def _done_ui(self, msg):
        self.running = False
        self.run_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        self.progress_label.configure(text=msg)
        self.progress["value"] = 100 if "完成" in msg else 0


def main():
    root = tk.Tk()
    RetroApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
