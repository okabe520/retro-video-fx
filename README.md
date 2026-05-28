# 复古视频效果处理器

给任何视频叠加 **噪点 + 像素化 + 高对比度 + 扫描线 + 晕影 + 闪烁 + 色差**，一键生成 VHS/80s/街机/恐怖片 风格的复古视频。

## 安装

```bash
pip install opencv-python numpy
```

## 使用

### 图形界面 (推荐)

```bash
python retro_gui.py
```

- 浏览选择视频 → 选预设风格 → 调缩放滑块 → 点开始
- 默认 `scale=0.3`，低配机友好；想高画质拉到 1.0

### 命令行

```bash
# 快速预览：VHS 预设，25% 缩放，只处理前 5 秒
python retro_fx.py input.mp4 -o output.mp4 --preset vhs --scale 0.25 -t 5

# 处理 30~40 秒片段
python retro_fx.py input.mp4 -o output.mp4 --preset horror --scale 0.3 --start 30 -t 10

# 自定义参数
python retro_fx.py input.mp4 -o out.mp4 --noise 0.08 --pixel 8 --contrast 2.0 --no-scanlines
```

### 参数说明

| 参数 | CLI | GUI | 说明 |
|------|-----|-----|------|
| 缩放 | `--scale 0.25` | 滑块 | 处理分辨率比例，越低越快 (0.1~1.0) |
| 起始时间 | `--start 30` | 输入框 | 从第几秒开始 |
| 时长 | `-t 5` | 结束秒 | 截取多长 (秒) |
| 亮度噪点 | `--noise 0.05` | 滑块 | 胶片颗粒感 (0~0.2) |
| 色彩噪点 | `--chroma-noise 0.05` | 滑块 | 颜色通道噪点 (0~0.15) |
| 像素块 | `--pixel 4` | 滑块 | 像素化程度 (1~16) |
| 对比度 | `--contrast 1.6` | 滑块 | 对比度倍数 (1.0~3.0) |
| 扫描线 | `--no-scanlines` | 勾选框 | CRT 横纹效果 |
| 晕影 | `--no-vignette` | 勾选框 | 四角暗角 |
| 闪烁 | `--no-flicker` | 勾选框 | 亮度随机波动 |
| 色差 | `--no-color-shift` | 勾选框 | R/B 通道偏移 |

### 预设风格

| 预设 | 特点 |
|------|------|
| **VHS** | 色彩噪点 + 扫描线 + 闪烁，90 年代录像带 |
| **80s** | 明显颗粒 + 色散偏移 + 强晕影 |
| **90s** | 轻微做旧，保留较多原始画质 |
| **ARCADE** | 大像素块 + 扫描线 + 高对比度 |
| **HORROR** | 强噪点 + 极高对比度 + 深暗角 |

## 性能提示

- i5-7300U / 8G 内存：建议 `--scale 0.25`，5 秒片段秒出
- 1080p 全片 `--scale 1.0` 会比较慢，视 CPU 而定
- 低分辨率反而更复古，不用追求 1.0
