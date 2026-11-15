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

## 注意

- GitHub 官方无 trending API，这里是页面抓取（服务端渲染，可直抓）；页面改版时改 `scripts/build_feed.py` 的正则
- raw URL 有 CDN 缓存，Inoreader 刷新频率按你的 Inoreader 设置走
- 测试记录（2026-11-15）：本地跑通，解析 12 条（当日页面实数），XML 合法，与 grep 计数交叉一致
