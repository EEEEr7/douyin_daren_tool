# XTeink · 达人微信号采集

**XTeink** 出品 · **© 2026 阅星曈 v1.1.0**

从 [精选联盟达人广场](https://buyin.jinritemai.com/dashboard/servicehall/daren-square) 筛选「3C数码家电 + 有联系方式」的达人，获取微信号并导出 Excel。

**默认稳妥模式**：每日目标 50 条，建议早/中/晚各运行 1 次，每次约 18 条，随机延迟 5–12 秒，自动去重。

## 安装

```bash
pip install -r requirements.txt
playwright install chromium
```

## 日常使用（推荐）

**图形界面（默认，显示进度）：**

```bash
# 推荐：双击项目目录中的 XTeink 抖音达人微信采集.exe
# 或
python main.py
# 或双击 start.bat
```

首次使用 exe 前，需在本机执行一次：

```bash
pip install -r requirements.txt
playwright install chromium
```

重新打包 exe（更新图标/代码后）：

```bash
build_exe.bat
```

**命令行模式（无界面）：**

```bash
python main.py --cli
```

### 建议调度（Windows 任务计划程序）

| 时间 | 命令 |
|------|------|
| 09:00 | `python main.py --session morning` |
| 14:00 | `python main.py --session noon` |
| 20:00 | `python main.py --session evening` |

也可直接运行 [`run_scheduled.bat`](run_scheduled.bat)（按当前时间自动选时段）。

**创建桌面快捷方式（XTeink 图标）：**

```bash
python create_desktop_shortcut.py
# 或双击 create_desktop_shortcut.bat
```

## 登录说明

1. 在 **Edge** 登录 [buyin.jinritemai.com](https://buyin.jinritemai.com)
2. **完全关闭 Edge** 后，打开 XTeink 界面，点击「从 Edge 导入」
3. 或使用「浏览器内登录」直接扫码/账号登录

## 稳妥策略说明

| 机制 | 说明 |
|------|------|
| 每日配额 | 目标 50 条/天，达到后自动停止 |
| 分次执行 | 每时段默认最多 18 条（3 次合计最多 54，留失败余量） |
| 随机延迟 | 每位达人间隔 5–12 秒 |
| UID 去重 | 已成功抓取的达人不再重复查看 |
| 按日合并 | 每次运行写入独立文件夹 `XTeink_YYYYMMDD_HHMM_上午/下午/晚上` |

## 输出

每次运行会创建独立结果文件夹，命名格式：

`output/XTeink_YYYYMMDD_HHMM_上午|下午|晚上/XTeink_达人联系方式.xlsx`

示例：`output/XTeink_20260526_1430_下午/XTeink_达人联系方式.xlsx`

列：达人昵称、UID、微信号、粉丝数、主页链接、抓取时间、备注、时段

## 可选参数

| 参数 | 说明 |
|------|------|
| `--session morning/noon/evening/auto` | 运行时段 |
| `--limit N` | 覆盖本次上限 |
| `--relogin` | 从 Edge 重新导入 Cookie |
| `--aggressive` | 快速模式（短延迟、无配额，不推荐） |
| `--firefox-profile PATH` | 指定 Firefox 配置（可选） |

## 注意事项

- 登录 Cookie 从 **Edge** 导入，采集使用内置 Chromium
- 批量查看联系方式仍有平台风控风险，请控制频率
- `data/` 含登录态与抓取记录，请勿泄露

---

**XTeink** · © 2026 阅星曈 v1.1.0
