# 💰 省钱比价 - 多平台比价工具

一站式购物/团购比价工具，帮你在淘宝、京东、拼多多、美团、抖音之间找到最优价格。

🌐 **在线使用**: https://compare.lovemysoul.top

## 功能

### 🛒 购物比价
输入商品关键词，自动比较淘宝、京东、拼多多的价格，选出最具性价比的选项。

### 🎫 团购比价
输入商品/服务，比较美团和抖音（抖省省）的团购价格。

### 🤖 AI 智能分析
接入商汤大模型（deepseek-v4-flash），智能分析各平台价格差异，给出购买建议。

## 技术架构

```
本地 Python 脚本（代理抓取真实数据）
        ↓ 生成 JSON
GitHub 仓库（数据存储 + 版本管理）
        ↓ push 触发自动部署
Cloudflare Pages（前端 + Functions API）
        ↓
compare.lovemysoul.top
```

## 项目结构

```
price-compare/
├── public/                 # 前端静态文件
│   ├── index.html          # 主页面
│   ├── css/style.css       # 样式（什么值得买风格）
│   └── js/app.js           # 交互逻辑
├── functions/api/          # Cloudflare Pages Functions
│   ├── search.js           # 购物搜索 API
│   ├── tuan.js             # 团购搜索 API
│   └── ai-analyze.js       # AI 智能分析 API（商汤）
├── data/                   # 预抓取数据
│   ├── shopping.json       # 购物比价数据
│   └── groupbuy.json       # 团购比价数据
├── scraper/                # 本地 Python 抓取脚本
│   ├── config.py           # 配置（代理、UA、超时）
│   ├── utils.py            # 工具函数
│   ├── run_all.py          # 一键抓取所有平台
│   ├── upload.py           # 上传数据到 GitHub
│   ├── jd_scraper.py       # 京东抓取
│   ├── taobao_scraper.py   # 淘宝抓取
│   ├── pdd_scraper.py      # 拼多多抓取
│   ├── meituan_scraper.py  # 美团团购抓取
│   └── douyin_scraper.py   # 抖音团购抓取
└── README.md
```

## 本地数据抓取

### 环境要求
- Python 3.10+
- `pip install requests beautifulsoup4 lxml`
- Clash Verge 代理运行中（端口 7897）

### 使用方法

```bash
cd scraper

# 抓取购物数据（京东/淘宝/拼多多）
python run_all.py --query "牛奶,纸巾,洗衣液" --type shopping

# 抓取团购数据（美团/抖音）
python run_all.py --query "火锅,奶茶" --type tuan

# 全部抓取
python run_all.py --query "牛奶,火锅" --type all

# 上传到 GitHub（触发 Cloudflare 自动部署）
python upload.py
```

### 各平台抓取状态

| 平台 | 方式 | 状态 |
|------|------|------|
| 京东 | 移动端 JSON API | ✅ 可用 |
| 淘宝 | H5 API / 网页解析 | ⚠️ 需登录态 |
| 拼多多 | 移动端页面 | ⚠️ 反爬严格 |
| 美团 | 搜索页解析 | ⚠️ 尽力而为 |
| 抖音 | 页面数据提取 | ⚠️ 尽力而为 |

> 抓取失败的平台会自动降级为模拟数据，前端会标注数据来源。

## 部署

项目通过 Cloudflare Pages 部署，push 到 GitHub main 分支即自动部署。

- **构建命令**: 无需构建
- **输出目录**: `public`
- **Functions**: `functions/`
- **环境变量**: `SENSENOVA_API_KEY`（商汤 API Key）

## 数据来源说明

- 🟢 **真实数据**: 通过本地脚本从各平台实时抓取
- 🟠 **模拟数据**: 当抓取失败时，使用合理的模拟数据作为降级方案
