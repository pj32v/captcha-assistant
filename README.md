# 验证码助手 (Captcha Assistant)

专为 **Windows 11** 量身定制的轻量级现代化桌面工具。

自动从 Windows「手机连接」（Phone Link）同步到系统的短信通知中高精度识别短信验证码，并自动复制到系统剪贴板，方便用户在电脑端直接 `Ctrl+V` 粘贴使用。

配备基于 **Windows 11 Fluent Design** 理念打造的高 DPI 自适应极简桌面界面，支持后台毫秒级扫描间隔自定义、剪贴板自动清理自由开关、开机静默自启与系统托盘后台守护。

---

## ✨ 核心特性

1. **零网络权限，100% 纯本地运行**：
   - 绝不引入任何网络通信模块，无任何上传行为，飞行模式下功能毫秒不差、完整可用。
   - 所有正则识别与 SQLite 读取均在本地 CPU / 内存中完成。
2. **银行级剪贴板安全防护**：
   - **阻断 Windows 剪贴板历史记录**：注入 `CanIncludeInClipboardHistory = 0`，验证码绝不会出现在 `Win+V` 历史记录面板中。
   - **阻断微软云剪贴板同步**：注入 `CanUploadToCloudClipboard = 0`，彻底防止验证码跨设备漫游同步到云端。
   - **支持自动超时清理与 Ctrl+V 延迟清理**：验证码粘贴后或超时后自动安全清空剪贴板，防止意外泄露。
3. **Windows 11 Fluent Design 桌面界面**：
   - 原生 DWM 柔和圆角与一体化浅灰标题栏。
   - 高 DPI 深度自适应 (2K/4K @ 125%~200%)，动态按内容自适应计算，文字清晰、杜绝截断。
4. **灵活自适应设置**：
   - **后台扫描间隔**：支持毫秒 (ms) 级自定义填写（如 1000ms、3000ms）。
   - **剪贴板自动清理**：提供自由开关与超时秒数配置。
   - **开机自启动**：可一键开启/关闭开机自启；开机时后台静默常驻托盘，不弹出窗口打扰。
5. **双向协同的托盘与窗口生命周期**：
   - 点击右上角关闭按钮自动隐藏至系统托盘，后台持续守护。
   - 双击托盘图标或右键选择「🖥 打开主界面」随时唤回窗口。
   - 通过托盘菜单「❌ 退出程序」安全退出。

---

## 🚀 运行与使用

### 1. 运行独立 EXE（推荐）
无需配置 Python 环境，直接下载绿色版单文件 EXE 即可使用：
👉 **[点击直接下载 CaptchaAssistant.exe (v1.3.0)](https://github.com/pj32v/captcha-assistant/releases/download/v1.3.0/CaptchaAssistant.exe)**

或者前往 [GitHub Releases 页面](https://github.com/pj32v/captcha-assistant/releases) 获取最新发布包。

### 2. 源码环境运行
确保已安装 Python 3.10+ (推荐 Python 3.14)：
```bash
# 1. 克隆代码仓库
git clone <本仓库地址>
cd 验证码助手

# 2. 安装必要依赖
pip install -r requirements.txt

# 3. 运行主程序
python main.py
```

### 3. 一键打包单文件 EXE
项目中已提供标准构建脚本：
```bash
# 直接双击运行或在终端执行
打包.bat
```
打包成功后，独立的单文件可执行程序将生成于 `dist/验证码助手.exe`。

---

## 🛠 技术架构

- **语言环境**：Python 3.14 (兼容 3.10+)
- **界面引擎**：Tkinter + 原生 Windows 11 DWM API (免安装体积巨大的 Qt 依赖，资源占用仅 ~25MB)
- **底层通信**：Windows Phone Link SQLite 只读快照解析 (`wpndatabase.db`)
- **剪贴板安全 API**：Windows User32 Ole32 Clipboard API (`RegisterClipboardFormatW`)
- **系统托盘**：Pystray (Win32 原生图标)
- **单实例控制**：Windows 全局命名互斥体 (`CreateMutexW`)

---

## 👥 作者与贡献者 (Contributors)

- **作者 / Maintainer**：[@pj32v](https://github.com/pj32v)

---

## 📄 开源许可证

本项目基于 [MIT License](LICENSE) 许可证开源。
