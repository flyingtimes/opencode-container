---
name: zlib
description: >
  从 Z-Library 下载电子书的自动化工具。当用户请求下载书籍、搜索电子书、
  或提到从zlib获取书籍时触发此技能。支持中文书名搜索。
  使用 opencli 控制宿主机已登录的 Chrome 浏览器完成搜索和下载。
---

# Z-Library 电子书下载技能 (opencli 版)

## 工作原理

通过 **opencli** 控制宿主机已登录的 Chrome 浏览器，复用 Z-Library 登录态，完成搜索→选书→下载全流程。

```
opencode 容器 → opencli CLI → 宿主 daemon → Chrome 扩展 → 已登录的 Z-Library
```

## 前置条件

1. 宿主机 opencli 已安装且与容器同版本
2. Chrome 已安装并启用 Browser Bridge 扩展
3. **Chrome 已登录 Z-Library**（zh.zlib.bz）—— 首次需手动登录
4. opencli daemon 运行中（`opencli doctor` 确认 Extension: connected）

## 一键下载

```bash
# 基本用法
bash skills/zlib/scripts/zlib_opencli.sh "书名"

# 示例
bash skills/zlib/scripts/zlib_opencli.sh "倚天屠龙记"
bash skills/zlib/scripts/zlib_opencli.sh "活着 余华"
bash skills/zlib/scripts/zlib_opencli.sh "The Martian"
```

输出格式：成功时最后一行输出 `__ZLIB_RESULT__` 前缀的 JSON。

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ZLIB_DOWNLOAD_DIR` | `~/Downloads` | 容器内为 `/workspace/storage/output`） |
| `OPENCLI` | `opencli` | opencli 命令路径 |

## 搜索词策略

| 书籍类型 | 推荐格式 | 示例 |
|----------|---------|------|
| 中文书籍 | "书名" 或 "书名 作者" | "活着" 或 "活着 余华" |
| 英文书籍 | "书名"（不加作者） | "The Martian" |

## 执行策略（分两步）

当用户请求下载书籍时，建议先搜索确认再下载：

```
用户: "帮我下载《倚天屠龙记》"
    │
    ▼
[1] 搜索（只搜不下载）
    bash skills/zlib/scripts/zlib_opencli.sh "倚天屠龙记" search
    → 输出前 5 条结果 JSON
    │
    ▼
[2] 向用户确认
    展示: 书名、作者、结果数
    │
    ├── 确认 → [3]
    └── 不是这本 → 换关键词重新 [1]
    │
    ▼
[3] 下载
    bash skills/zlib/scripts/zlib_opencli.sh "倚天屠龙记"
    → 下载第一本书，等待完成，输出路径
```

## Z-Library 页面结构（调试参考）

- **搜索**: 用 URL 直接导航 `https://zh.zlib.bz/s/{书名}?content_type=book`（比填表单更可靠）
- **搜索结果**: `<z-bookcard>` Web Component，书籍信息在 Shadow DOM 中
  - 链接: `shadowRoot.querySelector('a[href*="/book/"]')`
  - 标题: `shadowRoot.querySelector('h3')`（可能为空，从 href 解码）
  - 作者: `shadowRoot.querySelector('.authors')`
- **详情页下载链接**: `a.addDownloadedBook` 或 `a[href*="/dl/"]`，文本如 "epub, 10.97 MB"
- **无弹窗**: 点击下载链接直接触发浏览器下载，无需确认

## 脚本智能容错机制

脚本内置多项容错，无需人工干预：

1. **搜索结果相关性排序**：按书名与搜索词的关键词命中数排序，优先下载最匹配的书（避免搜索到同名无关书时下错）
2. **多结果自动重试**：某个版本的详情页 503/被重定向回搜索页/无下载链接时，自动切换到下一个搜索结果
3. **下载链接动态等待**：详情页的 `/dl/` 链接是 JS 动态渲染的，脚本最多重试 5 次（每次间隔 1.5s）
4. **详情页导航校验**：检查 `open` 后 URL 是否真正在 `/book/` 路径（Z-Library 有时将无效详情页重定向回搜索页）
5. **搜索词清洗**：自动去除书名号《》等特殊字符提升命中率


## 故障排查

| 错误 | 解决方案 |
|------|---------|
| opencli daemon 未运行 | 宿主机执行 `opencli doctor` |
| Extension: not connected | 检查 Chrome 扩展是否启用 |
| Chrome 未登录 Z-Library | 手动在 Chrome 中登录 zh.zlib.bz |
| CDN 超时 (522) | 等几秒重试 |
| 搜索无结果 | 简化搜索词 |
| 下载目录为空 | 检查 `$ZLIB_DOWNLOAD_DIR` 和浏览器下载设置 |
