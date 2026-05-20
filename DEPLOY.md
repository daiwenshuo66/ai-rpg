# AI RPG 部署教程 —— 云服务器篇

将游戏部署到阿里云 / 腾讯云 / 华为云等云服务器上，让别人通过浏览器访问你的游戏。

---

## 一、购买云服务器

任选一家，最便宜的即可：

| 平台 | 推荐产品 | 最低配置 | 参考价格 |
|------|---------|---------|---------|
| 阿里云 | 轻量应用服务器 | 2核2G | ~50元/月 |
| 腾讯云 | 轻量应用服务器 | 2核2G | ~45元/月 |
| 华为云 | HECS云耀服务器 | 2核2G | ~40元/月 |

购买时注意：
- **系统选 Ubuntu 22.04**（本教程基于 Ubuntu）
- 记住你的服务器 **公网 IP**
- 设置好 **root 密码** 或 SSH 密钥

---

## 二、开放端口

在云平台的 **安全组 / 防火墙** 中放行以下端口：

| 端口 | 用途 |
|------|------|
| 22   | SSH 登录（默认已开） |
| 80   | HTTP 网页访问 |
| 8000 | 备用（调试时直接用） |

各平台操作路径：
- **阿里云**：控制台 → 轻量应用服务器 → 防火墙 → 添加规则
- **腾讯云**：控制台 → 轻量应用服务器 → 防火墙 → 添加规则
- **华为云**：控制台 → 安全组 → 入方向规则 → 添加规则

---

## 三、连接服务器

用终端 SSH 登录（Windows 可用 PowerShell）：

```bash
ssh root@你的服务器IP
```

首次连接输入 `yes` 确认，然后输入密码。

---

## 四、安装环境

登录后依次执行：

```bash
# 更新系统
apt update && apt upgrade -y

# 安装 Python 和 pip
apt install -y python3 python3-pip python3-venv git

# 确认版本
python3 --version   # 需要 3.10+
```

---

## 五、上传代码

### 方式 A：用 Git（推荐）

先把项目推到 GitHub / Gitee，然后在服务器上拉取：

```bash
cd /opt
git clone https://github.com/你的用户名/ai-rpg.git
cd ai-rpg
```

### 方式 B：直接上传

在你本地电脑用 scp 传上去：

```powershell
# 在你的 Windows 电脑上执行
scp -r "D:\ai game1\*" root@你的服务器IP:/opt/ai-rpg/
```

---

## 六、配置项目

```bash
cd /opt/ai-rpg

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 设置环境变量（保护 API Key）

不要把 API Key 硬编码在代码里。创建环境变量文件：

```bash
cat > /opt/ai-rpg/.env << 'EOF'
API_KEY=sk-d18b031cf1d54ef1803c3aead2335adb
BASE_URL=https://api.deepseek.com
EOF

# 设置权限，只有 root 能读
chmod 600 /opt/ai-rpg/.env
```

---

## 七、测试运行

```bash
cd /opt/ai-rpg
source venv/bin/activate
source .env

# 先测试能不能跑起来
uvicorn web_app:app --host 0.0.0.0 --port 8000
```

在你的电脑浏览器访问 `http://你的服务器IP:8000`，能看到游戏页面就说明成功了。

`Ctrl+C` 停掉测试进程，继续下一步。

---

## 八、配置 Nginx 反向代理（用 80 端口访问）

```bash
# 安装 Nginx
apt install -y nginx

# 创建配置文件
cat > /etc/nginx/sites-available/ai-rpg << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 120s;
    }
}
EOF

# 启用配置
ln -sf /etc/nginx/sites-available/ai-rpg /etc/nginx/sites-enabled/default

# 测试配置无误后重启
nginx -t
systemctl restart nginx
```

---

## 九、设置后台自动运行（Systemd 服务）

让游戏在后台持续运行，服务器重启也能自动恢复：

```bash
cat > /etc/systemd/system/ai-rpg.service << 'EOF'
[Unit]
Description=AI RPG Game Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/ai-rpg
EnvironmentFile=/opt/ai-rpg/.env
ExecStart=/opt/ai-rpg/venv/bin/uvicorn web_app:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 启动服务
systemctl daemon-reload
systemctl enable ai-rpg    # 开机自启
systemctl start ai-rpg     # 立即启动

# 查看状态
systemctl status ai-rpg
```

---

## 十、验证部署

在你的电脑浏览器打开：

```
http://你的服务器IP
```

看到像素风游戏界面，输入文字能正常战斗，就部署成功了。

---

## 常用运维命令

```bash
# 查看服务状态
systemctl status ai-rpg

# 查看实时日志
journalctl -u ai-rpg -f

# 重启服务（改了代码之后）
systemctl restart ai-rpg

# 停止服务
systemctl stop ai-rpg
```

---

## 更新代码

```bash
cd /opt/ai-rpg

# 如果用 Git
git pull

# 如果手动上传，scp 覆盖文件后：
systemctl restart ai-rpg
```

---

## 可选：绑定域名 + HTTPS

如果你有域名，可以进一步配置：

### 1. 域名解析

在域名服务商后台添加 A 记录：
- 主机记录：`@` 或 `game`
- 记录值：你的服务器 IP

### 2. 申请免费 SSL 证书

```bash
# 安装 certbot
apt install -y certbot python3-certbot-nginx

# 申请证书（替换成你的域名）
certbot --nginx -d 你的域名.com

# 自动续期已配置，无需额外操作
```

之后就可以用 `https://你的域名.com` 访问了。

---

## 项目文件说明

```
/opt/ai-rpg/
├── web_app.py         ← Web 服务入口
├── static/index.html  ← 前端页面
├── config.py          ← 配置（从环境变量读取）
├── engine.py          ← 游戏引擎
├── ai_parser.py       ← AI 解析层
├── ai_narrator.py     ← AI 叙事层
├── game_state.py      ← 状态管理
├── .env               ← API Key（不要提交到 Git）
└── venv/              ← Python 虚拟环境
```

---

## 常见问题

**Q: 访问页面显示 502 Bad Gateway**
A: 游戏服务没启动。执行 `systemctl start ai-rpg`，然后 `journalctl -u ai-rpg -f` 看日志排查。

**Q: AI 回复报错或超时**
A: 检查服务器能否访问 DeepSeek API：`curl https://api.deepseek.com`。如果不通，可能需要服务器开启外网访问。

**Q: 如何看同时有多少人在玩**
A: 查看日志中的 session 数量：`journalctl -u ai-rpg --since "1 hour ago" | grep "api/new" | wc -l`
