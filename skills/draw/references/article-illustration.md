# Draw技能用于文章配图

draw不仅用于PPT配图，也适用于科普文章/博客/Medium文章的配图。

## 工作流

1. 写完文章后，统计章节数，规划哪些章节需要配图（≥50%）
2. 为每张图写英文prompt（主体+风格+氛围+`white background`+`16:9 ratio`）
3. 批量生成到`文章名-images/`子目录
4. 用相对路径`![描述](子目录/xxx.png)`嵌入markdown

## 批量脚本模板

```python
#!/usr/bin/env python3
"""批量文章配图生成"""
import subprocess, sys, os

DRAW = ".opencode/skills/draw/scripts/draw.py"  # 相对 /workspace
IMG_DIR = "<文章所在目录>/<文章名>-images"
os.makedirs(IMG_DIR, exist_ok=True)

IMAGES = [
    ("概念图.png", "conceptual illustration of..., white background, 16:9 ratio"),
    ("对比图.png", "before and after comparison..., white background, 16:9 ratio"),
]
for filename, prompt in IMAGES:
    out = os.path.join(IMG_DIR, filename)
    r = subprocess.run([sys.executable, DRAW, prompt, "-o", out],
                       capture_output=True, text=True, timeout=300)
    print(f"  {filename}: {'OK' if r.returncode == 0 else 'FAIL'}")
```

## Prompt要点

- **英文>>中文**，中文prompt质量明显差
- 文章配图建议`white background`（适配浅色主题）
- 比例写末尾：`16:9 ratio`
- 概念图用`conceptual illustration`、`infographic`、`minimalist style`
- 对比图用`before and after comparison`、`split screen`
- 每张图1-2句话描述核心视觉意图即可

## 文件组织

文章和图片目录同级放置，用相对路径引用（容器内均在 /workspace 下，宿主对应项目目录）：
```
/workspace/
├── 我的文章.md          ← 文中写 ![desc](my-article-images/xxx.png)
└── my-article-images/   ← draw生成的图片
    ├── concept.png
    └── comparison.png
```
