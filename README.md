# gh-trending-feed

GitHub Actions 每天（约 01:30 UTC，trending 刷新后）抓 `github.com/trending`，生成 RSS（`trending.xml`）提交到本仓库。Inoreader 直接订阅 raw URL，不依赖 RSSHub，不依赖本地服务。

## 订阅 URL（push 并跑一次后）

```
https://raw.githubusercontent.com/<你的用户名>/gh-trending-feed/main/trending.xml
```

## 使用

1. 新建 GitHub 仓库，把本目录内容 push 上去
2. Actions 页手动 Run 一次 workflow（workflow_dispatch），确认 trending.xml 生成
3. Inoreader → Add feed → 粘贴上面的 raw URL（建议起个 tag，配 filter rules）

## 可调参数

- `.github/workflows/trending-feed.yml` 里 `SINCE`：daily / weekly / monthly；`LANGUAGE`：如 `python`（留空=全部语言）
- cron 时间：改 `schedule`

## 翻译

每条描述用 Google 免费接口（`translate.googleapis.com`，免 key）自动译成中文；失败或限流时保留原文（单条重试一次）。设 `TRANSLATE=false` 可关。仓库名保持原文不译。

线上验证（2026-11-15 14:21 UTC，run 43723887894）：12/12 描述为中文，XML 合法。注意 Inoreader 已缓存的条目仍是英文，下一次刷新进来的新条目才是中文。

## 条目字段（内容 / 功能 / 趋势）

每条 item 的 description 结构：`功能：<中文描述> ｜ 标签：<topics> ｜ 主页：<homepage> ｜ fork N｜总star N ｜ 趋势：<...> ｜ 最近推送：<日期>`

- 功能（描述）：优先取 trending 页面原文再翻译；页面无描述时回退 GitHub API 的 description
- 标签 / 主页 / fork / 总star：来自 GitHub REST API（`api.github.com/repos/<owner>/<repo>`），同时写入 RSS `category`
- 趋势：与仓库内 `history.csv` 的前一天快照对比 —— `昨日第N→今日第M（star +x）`，未在前一天快照中出现则 `新上榜`。首次运行全部显示「新上榜」，第二次起才有真实趋势
- `history.csv` 由脚本每次运行追加（同一天重复运行不追加），是趋势的唯一数据源，别删

## 注意

- GitHub 官方无 trending API，这里是页面抓取（服务端渲染，可直抓）；页面改版时改 `scripts/build_feed.py` 的正则
- raw URL 有 CDN 缓存，Inoreader 刷新频率按你的 Inoreader 设置走
- 测试记录（2026-11-16）：本地跑通，解析 12 条（当日页面实数），XML 合法；标题链接提取用三个独立实现交叉一致（python re / `grep -oP '(?s)...'` 按 article 块 / awk 记录切分），sponsors 链接不再误抓（页面实有 2 个 sponsor href，提取结果 0）。趋势字段用人工构造的昨日快照验证：排名移动与 star 增量正确、新条目显示「新上榜」、重跑不追加重复行
- 口径更正：此前那次「grep 交叉一致」无效——POSIX ERE 不支持惰性量词，且 grep 逐行处理不跨行，当时的 0 是假阴性；现在的复查必须用 `grep -P` 或按 article 块处理
