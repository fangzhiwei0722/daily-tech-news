# 📡 每日编程技术资讯

自动收集 GitHub、Hacker News、Reddit r/programming 的编程相关最新技术，每日汇总。

## 查看当日报告

报告按照 `github_daily_tech_YYYY-MM-DD.md` 文件保存在仓库根目录。

## 触发方式

- **定时触发**：每天 UTC 0:00（北京时间 8:00）自动运行
- **手动触发**：在 GitHub Actions 页面点击 "Run workflow"

## 本地运行

```bash
python3 github_daily_tech_collector.py
```

需要 `gh` CLI 已登录，且有 GitHub API 访问权限。

## 数据来源

| 来源 | 内容 |
|------|------|
| GitHub API | 按语言分类的热门仓库、活跃项目 |
| Hacker News | 编程相关热门帖子 |
| Reddit r/programming | 热门讨论帖子 |
