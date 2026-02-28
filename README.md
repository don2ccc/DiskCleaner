# 💎 DiskCleaner Pro

<div align="center">

**智能 C 盘清理工具 | 深度扫描 · AI 分析 · 安全清理**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)](https://www.microsoft.com/windows)

[功能特性](#-功能特性) • [快速开始](#-快速开始) • [使用指南](#-使用指南) • [AI 功能](#-ai-功能可选) • [常见问题](#-常见问题)

</div>

---

## 📖 简介

DiskCleaner Pro 是一款专为 Windows C 盘设计的智能清理工具，通过深度扫描和智能规则，帮助用户快速识别和清理占用大量空间的无用目录。

**本工具扫描出来的目录，请您一定要再三仔细确认，软件作者不对扫描结果，以及删除对应文件夹产生的后果，负任何责任！**

### 🎯 为什么选择 DiskCleaner？

- ✅ **智能扫描**：自动排除系统关键目录，避免误删
- ✅ **双重规则**：基于大小 + 时间的精准判断
- ✅ **AI 分析**：接入 DeepSeek/Gemini 等 AI 模型，智能分类目录用途
- ✅ **安全保护**：默认移入回收站，支持一键恢复
- ✅ **现代化 UI**：深色主题 + 实时进度显示
- ✅ **缓存加速**：二次扫描速度提升 3-5 倍

---

## ✨ 功能特性

### 🔍 智能扫描

- **自动排除系统目录**：Windows、Program Files、ProgramData 等
- **实时进度显示**：当前扫描路径 + 已发现目录数
- **两阶段扫描**：优先验证缓存，再增量全盘扫描

### 🎯 清理规则

支持三种预设方案，可在「设置」中切换：

| 方案 | 高优先级 | 普通优先级 | 适用场景 |
|------|---------|----------|---------|
| 🐢 **保守** | 2GB + 1年 | 1GB + 半年 | 谨慎清理，避免误删 |
| ⚖️ **普通** (推荐) | 1GB + 半年 | 500MB + 3个月 | 平衡空间与安全 |
| 🚀 **激进** | 500MB + 3个月 | 200MB + 1个月 | 最大化释放空间 |

### 🤖 AI 分析（可选）

支持接入外部 AI 模型，智能分析目录用途：

- **DeepSeek**：高性价比，推荐
- **Google Gemini**：免费额度大
- **OpenAI**：高精度

AI 分析结果示例：
- `临时缓存` (95%) - 可安全删除的临时文件
- `应用数据` (80%) - 应用程序缓存目录
- `未知目录` (60%) - 需谨慎处理

### 🛡️ 安全保护

- **回收站模式**：默认删除方式，支持恢复
- **直接删除**：高级选项，谨慎使用
- **二次确认**：删除前弹窗确认，防止误操作
- **详细日志**：所有操作记录到 `disk-cleaner.log`

### 🎨 用户体验

- **右键菜单**：表格中右键目录 → 在资源管理器中打开
- **清除缓存**：一键清空扫描缓存，重新全盘扫描
- **快捷操作**：快速清理临时文件（开发中）

---

## 🚀 快速开始

### 方式 1：exe 版本（推荐，无需 Python）

1. 前往 [Releases](https://github.com/don2ccc/DiskCleaner/releases) 页面
2. 下载 `DiskCleaner.exe`
3. 双击运行，立即开始

### 方式 2：源码版本（适合开发者）

#### 前置要求

- **Python 3.8+**
- **Windows 10/11**

#### 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/YOUR_USERNAME/DiskCleaner.git
cd DiskCleaner

# 2. 双击运行
launch.bat
```

脚本会自动：
- ✅ 检查 Python 环境
- ✅ 安装所有依赖
- ✅ 启动 AI 服务（如果已配置）
- ✅ 打开主界面

---

## 📘 使用指南

### 1️⃣ 基础扫描

1. 点击「🔍 开始扫描」按钮
2. 等待扫描完成（首次约 2-5 分钟）
3. 查看结果列表，优先级标注为 `HIGH` / `NORMAL`

### 2️⃣ 查看详情

- 右键点击任意目录 → 「在资源管理器中打开」
- 手动检查目录内容，确认是否需要清理

### 3️⃣ 执行清理

1. 勾选要删除的目录
2. 点击「🗑️ 删除选中」
3. 确认弹窗信息
4. 文件将移入回收站

### 4️⃣ 调整规则

点击「⚙️ 设置」→ 选择预设方案或手动调整参数：

- **高优先级**：大小阈值 + 未访问天数
- **普通优先级**：较小阈值 + 较短天数

---

## 🤖 AI 功能（可选）

### 为什么使用 AI？

AI 分析可以：
- 自动识别目录类型（临时缓存、应用数据、用户文件等）
- 给出可信度评分，辅助决策
- 减少误删风险

### 配置步骤

#### 使用 DeepSeek（推荐）

1. 注册 [DeepSeek](https://platform.deepseek.com/) 账号
2. 获取 API Key
3. 在主界面点击「🤖 AI 配置」
4. 填写信息：
   - **提供商**：选择 `deepseek`
   - **API Key**：粘贴你的密钥
5. 点击「🧪 测试 API Key」验证
6. 保存并启动服务

#### 使用 Google Gemini（免费）

1. 前往 [Google AI Studio](https://makersuite.google.com/app/apikey)
2. 创建 API Key
3. 配置时选择 `gemini` 提供商

### 使用 AI 分析

1. 扫描完成后，勾选目标目录
2. 点击「🤖 AI 分析」
3. 等待分析完成（每个目录约 1-3 秒）
4. 查看「AI 分析」列的结果

### 调试 AI 问题

如果 AI 分析失败：

1. 点击「📝 查看服务日志」
2. 查看错误信息（API Key 无效、网络问题等）
3. 双击 `restart_ai_service.bat` 重启服务

---

## 🛠️ 开发者指南

### 项目结构

```
DiskCleaner/
├── gui_main.py              # 主界面
├── ai_proxy.py              # AI 代理服务
├── core/
│   ├── scanner.py           # 目录扫描
│   ├── rules.py             # 清理规则
│   ├── ai_analyzer.py       # AI 分析
│   ├── cleaner.py           # 删除操作
│   ├── smart_rules.py       # 智能识别
│   ├── scan_cache.py        # 扫描缓存
│   └── logger.py            # 日志系统
├── launch.bat               # 一键启动
├── build_exe.bat            # 打包脚本
└── requirements.txt         # 依赖清单
```

### 本地开发

```bash
# 安装依赖
pip install -r requirements.txt

# 运行主程序
python gui_main.py

# 启动 AI 服务（可选）
python ai_proxy.py
```

### 打包成 exe

```bash
# 双击运行
build_exe.bat

# 输出位置
dist/DiskCleaner.exe
```

---

## ❓ 常见问题

### Q1: 扫描速度慢？

**A**: 首次扫描需要 2-5 分钟。后续扫描会使用缓存，速度提升 3-5 倍。

### Q2: AI 服务无法启动？

**A**: 检查以下几点：
1. API Key 是否正确
2. 网络是否能访问 API 地址
3. 端口 10089 是否被占用
4. 查看 `ai_service.log` 日志

### Q3: 删除的文件可以恢复吗？

**A**: 可以！默认使用「移入回收站」模式，在回收站中可以恢复。

### Q4: 会误删系统文件吗？

**A**: 不会！扫描时自动排除 Windows、Program Files 等系统目录。

### Q5: 支持 Mac/Linux 吗？

**A**: 目前仅支持 Windows。核心代码跨平台，但 UI 和路径逻辑针对 Windows 优化。

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

### 开发路线图

- [ ] 支持 D/E 盘扫描
- [ ] 空间占用可视化（树形图/饼图）
- [ ] 自动清理计划任务
- [ ] 多语言支持（英文）

---

## 📄 许可证

本项目采用 [MIT License](LICENSE) 开源。

---

## 💬 反馈与支持

- **Bug 报告**：[提交 Issue](https://github.com/YOUR_USERNAME/DiskCleaner/issues)
- **功能建议**：欢迎在 Issues 中讨论
- **联系作者**：[YOUR_EMAIL]

---

<div align="center">

**如果这个项目帮到了你，请给一个 ⭐️ Star！**

Made with ❤️ by [YOUR_NAME]

</div>
