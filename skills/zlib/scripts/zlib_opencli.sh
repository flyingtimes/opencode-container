#!/bin/bash
# Z-Library 电子书下载工具（opencli 版）
# 用法: ./zlib_opencli.sh "书籍名称" [search|download] [book_index]
#   book_index: 下载第几本（从1开始，按相关性排序后），默认 1。仅在 download 模式生效。
# 依赖: opencli 已安装、宿主 daemon 运行中、Chrome 已登录 Z-Library

set -o pipefail
trap '' PIPE  # 忽略 SIGPIPE（opencli 导航到下载链接时浏览器行为可能触发）

# ===== 配置 =====
SESSION="zlib"
ZLIB_BASE="https://zh.zlib.bz"
DOWNLOAD_DIR="${ZLIB_DOWNLOAD_DIR:-$HOME/Downloads}"
OPENCLI="${OPENCLI:-opencli}"

# ===== 颜色 =====
G='\033[0;32m'; Y='\033[1;33m'; R='\033[0;31m'; B='\033[0;34m'; N='\033[0m'
log_info()  { echo -e "${G}[INFO]${N} $1"; }
log_error() { echo -e "${R}[ERROR]${N} $1" >&2; }
log_warn()  { echo -e "${Y}[WARN]${N} $1" >&2; }
log_step()  { echo -e "${B}[STEP]${N} $1" >&2; }

# ===== 前置检查 =====
check_env() {
  log_step "检查 opencli 环境..."
  if ! command -v "$OPENCLI" &>/dev/null; then
    log_error "opencli 未安装或不在 PATH"
    exit 1
  fi
  local status
  status=$("$OPENCLI" daemon status 2>&1 || true)
  if echo "$status" | grep -q "not running"; then
    log_error "opencli daemon 未运行，请在宿主机执行: opencli doctor"
    exit 1
  fi
  if ! echo "$status" | grep -q "Extension: connected"; then
    log_error "Browser Bridge 扩展未连接，请检查 Chrome 扩展是否启用"
    exit 1
  fi
  log_info "opencli 环境正常"
}

# ===== 搜索词优化 =====
optimize_term() {
  local book="$1"
  # 英文书名只用第一个词
  if echo "$book" | grep -qE "^[a-zA-Z0-9: .,-]+$"; then
    echo "$book" | awk '{print $1}'
  else
    # 去除常见中文标点（书名号《》等）以提升搜索命中率
    echo "$book" | sed 's/[《》【】「」『』]//g'
  fi
}

# ===== JS 片段（用单引号 heredoc 避免 bash 干扰）=====
read -r -d '' JS_SEARCH <<'JSEOF' || true
(() => {
  const cards = document.querySelectorAll('z-bookcard');
  const items = [];
  for (let i = 0; i < Math.min(10, cards.length); i++) {
    try {
      const shadow = cards[i].shadowRoot;
      const link = shadow.querySelector('a[href*="/book/"]');
      const titleEl = shadow.querySelector('h3');
      let title = titleEl ? titleEl.textContent.trim() : '';
      if (!title && link) {
        const parts = link.getAttribute('href').split('/');
        if (parts.length > 3) title = decodeURIComponent(parts[parts.length-1].replace('.html',''));
      }
      const authorEl = shadow.querySelector('.authors');
      items.push({ title, author: authorEl ? authorEl.textContent.trim() : '', href: link ? link.href : '' });
    } catch(e) {}
  }
  return JSON.stringify(items);
})()
JSEOF

read -r -d '' JS_DOWNLOAD <<'JSEOF' || true
(() => {
  const links = document.querySelectorAll('a.addDownloadedBook, a[href*="/dl/"]');
  const found = [];
  for (const a of links) {
    const text = a.textContent.trim();
    const href = a.href;
    if (href && href.includes('/dl/') && !text.match(/libre|mirror|external|slow|proxy|donate/i)) {
      found.push({ text, href });
    }
  }
  return JSON.stringify(found);
})()
JSEOF

# 检查当前 URL 是否在详情页（而非被重定向回搜索页）
read -r -d '' JS_IS_DETAIL <<'JSEOF' || true
(() => {
  // 详情页 URL 含 /book/，搜索页含 /s/
  return location.pathname.includes('/book/') ? 'yes' : 'no';
})()
JSEOF

# ===== 搜索并提取结果 =====
search_books() {
  local term="$1"
  local encoded
  encoded=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$term")
  local search_url="$ZLIB_BASE/s/${encoded}?content_type=book"

  log_step "搜索: $term"
  "$OPENCLI" browser "$SESSION" open "$search_url" >/dev/null 2>&1
  sleep 4

  # 提取搜索结果
  "$OPENCLI" browser "$SESSION" eval "$JS_SEARCH" 2>/dev/null
}

# ===== 从详情页提取下载链接（带重试）=====
extract_download_link() {
  local dl_json=""
  local attempt
  for attempt in 1 2 3 4 5; do
    dl_json=$("$OPENCLI" browser "$SESSION" eval "$JS_DOWNLOAD" 2>/dev/null || echo "")
    local dl_count
    dl_count=$(echo "$dl_json" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
    if [ "$dl_count" -gt 0 ] 2>/dev/null; then
      echo "$dl_json"
      return 0
    fi
    sleep 1.5
  done
  echo "$dl_json"
  return 1
}

# ===== 打开详情页并下载 =====
# 返回 0=成功, 1=此书不可用（应换下一本）, 2=下载失败
download_book() {
  local book_href="$1"
  log_step "打开书籍详情页..."
  "$OPENCLI" browser "$SESSION" open "$book_href" >/dev/null 2>&1
  sleep 4

  # 检查是否真的导航到了详情页（Z-Library 有时将无效/503 的详情页重定向回搜索页）
  local is_detail
  is_detail=$("$OPENCLI" browser "$SESSION" eval "$JS_IS_DETAIL" 2>/dev/null | tr -d '"' || echo "no")
  if [ "$is_detail" != "yes" ]; then
    log_warn "详情页不可用（被重定向回搜索页），尝试下一个结果"
    return 1
  fi

  # 提取下载链接（带重试，应对动态渲染）
  local dl_json
  dl_json=$(extract_download_link) || true

  local dl_href dl_text
  dl_href=$(echo "$dl_json" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[0]['href'] if d else '')" 2>/dev/null || echo "")
  dl_text=$(echo "$dl_json" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[0]['text'] if d else '')" 2>/dev/null || echo "")

  if [ -z "$dl_href" ]; then
    log_warn "此书详情页无下载链接，尝试下一个结果"
    return 1
  fi

  log_info "找到下载: $dl_text"

  # opencli 控制的是宿主机 Chrome，下载文件落到浏览器默认下载目录
  local dl_dir="$DOWNLOAD_DIR"
  if [ ! -d "$dl_dir" ]; then
    dl_dir="${HOME}/Downloads"
  fi

  # 记录下载前文件列表
  local before_list
  before_list=$(ls -1t "$dl_dir" 2>/dev/null | head -1)

  log_step "触发下载..."
  "$OPENCLI" browser "$SESSION" open "$dl_href" >/dev/null 2>&1

  # 等待下载完成
  log_step "等待下载完成..."
  mkdir -p "$dl_dir"
  local elapsed=0 timeout_sec=60 latest=""
  while [ $elapsed -lt $timeout_sec ]; do
    if ! ls "$dl_dir"/*.crdownload 2>/dev/null | grep -q .; then
      latest=$(ls -1t "$dl_dir" 2>/dev/null | head -1)
      if [ -n "$latest" ] && [ "$latest" != "$before_list" ]; then
        sleep 2  # 确保写完
        break
      fi
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done

  if [ -z "$latest" ] || [ "$latest" = "$before_list" ]; then
    log_error "未检测到新下载文件，请检查浏览器下载目录（$dl_dir）"
    return 2
  fi

  local full_path="$dl_dir/$latest"
  local file_size
  file_size=$(du -h "$full_path" 2>/dev/null | cut -f1 || echo "?")

  if [[ "$latest" == *.crdownload ]]; then
    log_error "下载未完成: $latest"
    return 2
  fi

  echo ""
  echo "========================================"
  echo -e "${G}✓ 下载完成${N}"
  echo "  文件: $latest"
  echo "  大小: $file_size"
  echo "  路径: $full_path"
  echo "========================================"
  echo "__ZLIB_RESULT__{\"success\":true,\"file\":\"$latest\",\"path\":\"$full_path\",\"size\":\"$file_size\"}"
  return 0
}

# ===== 主函数 =====
main() {
  if [ -z "${1:-}" ]; then
    echo "用法: $0 \"书籍名称\" [search|download]"
    echo "示例: $0 \"三体\"  |  $0 \"活着 余华\"  |  $0 \"The Martian\""
    exit 1
  fi

  local book_name="$1"
  local mode="${2:-download}"
  local book_index="${3:-1}"

  # 校验 book_index（仅 download 模式使用，但提前校验更安全）
  if ! [[ "$book_index" =~ ^[0-9]+$ ]] || [ "$book_index" -lt 1 ]; then
    log_error "book_index 必须是 >=1 的整数，收到: $book_index"
    exit 1
  fi

  echo ""
  echo "========================================"
  echo "  Z-Library 下载工具 (opencli 版)"
  echo "========================================"

  check_env

  local term
  term=$(optimize_term "$book_name")

  # 搜索
  local results
  results=$(search_books "$term")

  local count
  count=$(echo "$results" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

  if [ "$count" = "0" ]; then
    log_error "搜索无结果: $term"
    exit 1
  fi

  # 按书名与搜索词的相关性排序（优先下载最匹配的，避免下错书）
  # 评分逻辑：搜索词的每个关键词出现在书名中即加分；全部命中排最前
  results=$(echo "$results" | python3 -c "
import json, sys, re
term = sys.argv[1]
books = json.load(sys.stdin)
# 提取搜索词关键词（中英文混合：中文按字/词，英文按空格分词）
keywords = set()
for part in term.lower().split():
    keywords.add(part)
# 中文：连续中文字符段作为关键词
for m in re.findall(r'[\u4e00-\u9fff]+', term):
    if len(m) <= 4:
        keywords.add(m)
    else:
        keywords.add(m[:2])  # 长中文词取前两字

def score(book):
    title = (book.get('title') or '').lower()
    s = 0
    for kw in keywords:
        if kw and kw in title:
            s += len(kw)  # 越长的关键词命中权重越高
    return -s  # 降序（高分在前）

books.sort(key=score)
print(json.dumps(books, ensure_ascii=False))
" "$book_name" 2>/dev/null || echo "$results")

  log_info "找到 $count 个结果（按相关性排序）"
  echo "$results" | python3 -c "
import json,sys
for i,b in enumerate(json.load(sys.stdin)[:5]):
    print(f'  [{i+1}] {b[\"title\"]}  {b[\"author\"]}')
" 2>/dev/null

  if [ "$mode" = "search" ]; then
    echo "__ZLIB_RESULT__{\"found\":true,\"results\":$results}"
    exit 0
  fi

  # 下载：遍历搜索结果，逐个尝试，直到成功
  # （有些版本的详情页可能 503 或被重定向，需要 fallback 到下一个结果）
  local total
  total=$(echo "$results" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

  # 构造尝试顺序：优先下载用户指定的第 N 本（book_index），其余按相关性顺序作为 fallback
  local target=$((book_index - 1))
  if [ "$target" -ge "$total" ]; then
    log_error "指定的第 ${book_index} 本超出范围（共 ${total} 个结果）"
    exit 1
  fi
  if [ "$book_index" -ne 1 ]; then
    log_info "指定下载第 ${book_index} 本（fallback 时按相关性顺序尝试其余）"
  fi
  local order
  order=$(python3 -c "
import sys
total, target = $total, $target
order = [target] + [i for i in range(total) if i != target]
print(' '.join(map(str, order)))
")

  local idx
  for idx in $order; do
    local href title
    href=$(echo "$results" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[$idx]['href'])" 2>/dev/null)
    title=$(echo "$results" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[$idx]['title'])" 2>/dev/null)
    log_info "尝试 [$((idx+1))/$total]: $title"

    download_book "$href"
    local rc=$?
    if [ $rc -eq 0 ]; then
      exit 0
    elif [ $rc -eq 1 ]; then
      # 此书不可用，换下一本
      continue
    else
      # 下载本身失败（rc=2），不再换书
      exit 1
    fi
  done

  log_error "所有 $total 个搜索结果均无法下载"
  exit 1
}

main "$@"
