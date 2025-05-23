# HoneyPot

HoneyPot 是一个基于 FastAPI 构建的蜜罐系统，用于记录和分析潜在攻击行为。通过模拟登录与注册接口，捕获恶意请求并将其存储在数据库中以供后续分析。

## 📦 功能特性

 - 模拟登录和注册页面。
 - 记录访问者的 IP 地址、User-Agent 和提交的数据。
 - 长度攻击防范，避免塞爆数据库。

## 🔧 安装与部署

1. 克隆仓库
   ```bash
   git clone https://github.com/qqAys/honeypot.git
   cd honeypot
   ```

2. 配置数据库

   ```bash
   mv .env.example .env
   vim .env
   ```

3. 构建并启动

   ```bash
   docker compose up -d
   ```

## 🪜 用户真实 IP 获取

https://github.com/qqAys/honeypot/blob/b79048843ad74c0f368ceab66f977767e98ae4fb/main.py#L175

如果您将 HoneyPot 部署在中间件（如 Nginx、Caddy 等）之后。此时，需要确保中间件转发请求时添加 `X-Real-IP` 请求头，以便 HoneyPot 能够正确获取用户的真实 IP 地址。

### Caddyfile

```Caddyfile
honeypot.qqays.xyz {
    reverse_proxy 127.0.0.1:8200 {
        header_up X-Real-IP {http.request.remote.host}
    }
}
```

## ⚠️ 注意事项

 - 本项目为蜜罐系统，请勿用于非法用途。
 - 建议部署于内网或测试环境中。
 - 如需增强安全性，建议添加 HTTPS 支持。

### 👮 免责声明

参见 [disclaimer.md](./disclaimer.md)

## 🪪 许可证

This project is licensed under the MIT License.
