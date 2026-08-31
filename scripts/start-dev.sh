#!/usr/bin/env bash
# =============================================================================
# SmartTaskBoard 一键开发启动脚本
#
# 用法:
#   cd ~/Projects/SmartTaskBoard
#   ./scripts/start-dev.sh
#
# 它会自动完成:
#   1. 检查 Docker 是否运行
#   2. 启动 PostgreSQL (docker compose)
#   3. 激活项目 Python 3.12 虚拟环境 (.venv)
#   4. 从 .env 安全读取配置 (数据库密码 / AI_API_KEY 等, 绝不打印)
#   5. 应用 Alembic 数据库迁移
#   6. 启动 FastAPI 后端 + Vite 前端 (后台运行)
#
# 注意:
#   - 所有密钥 (POSTGRES_PASSWORD / AI_API_KEY / JWT_SECRET_KEY) 都来自 .env
#     (.env 已被 Git 忽略), 脚本内不硬编码任何密钥。
#   - 若 .env 缺失 JWT_SECRET_KEY, 会本机生成并写回 .env。
#   - 停止服务: pkill -f 'uvicorn app.main' ; pkill -f vite
# =============================================================================
set -euo pipefail

# 让 brew / uv 管理的命令在 PATH 中可见
export PATH="$HOME/.local/bin:$HOME/.homebrew/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

# 定位到项目根目录 (脚本位于 <项目根>/scripts/ 下)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo "==> [1/6] 检查 Docker 是否运行"
if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker 未运行。请先打开 Docker Desktop 应用并等待左下角状态变为绿色/ready。"
  exit 1
fi

echo "==> [2/6] 启动 PostgreSQL (docker compose)"
docker compose up -d
for i in $(seq 1 30); do
  if docker exec smart-task-board-postgres pg_isready -U smarttaskboard_test -d smarttaskboard_core_test >/dev/null 2>&1; then
    echo "    PostgreSQL 就绪"
    break
  fi
  sleep 2
done

echo "==> [3/6] 激活 Python 虚拟环境 (.venv, Python 3.12)"
if [ ! -d .venv ]; then
  echo "    .venv 不存在，正在创建..."
  python3.12 -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -e ".[dev]"
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> [4/6] 校验 .env 配置 (不打印任何密钥; 应用自身会读取 .env)"
if [ ! -f .env ]; then
  echo "ERROR: .env 不存在。请参考 .env.example 创建 .env 并填入 DATABASE_URL / AI_API_KEY 等。"
  exit 1
fi

# 若缺少 JWT 密钥则本机生成 (不打印值)
if ! grep -q '^JWT_SECRET_KEY=' .env; then
  printf 'JWT_SECRET_KEY=%s\n' "$(openssl rand -base64 48)" >> .env
  echo "    JWT_SECRET_KEY 未设置，已本机生成并写回 .env"
fi

# 校验关键敏感变量存在 (不打印值, 仅检查字段是否存在)
grep -q '^DATABASE_URL=' .env || { echo "ERROR: DATABASE_URL 未设置，请在 .env 中配置"; exit 1; }
grep -q '^AI_API_KEY=' .env  || { echo "ERROR: AI_API_KEY 未设置，请在 .env 中配置"; exit 1; }
echo "    DATABASE_URL / AI_API_KEY / JWT_SECRET_KEY 均已就绪 (不显示值)"

echo "==> [5/6] 应用 Alembic 数据库迁移 (upgrade head)"
python -m alembic upgrade head

echo "==> [6/6] 启动后端 (FastAPI) 与前端 (Vite)"
# 后端
nohup python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 \
  > /tmp/stb-backend.log 2>&1 < /dev/null &
disown
# 前端
cd web
nohup npm run dev -- --host 127.0.0.1 --port 5173 \
  > /tmp/stb-frontend.log 2>&1 < /dev/null &
disown
cd ..

# 等待服务起来
sleep 6

echo
echo "============================================================"
echo " SmartTaskBoard 开发环境已启动"
echo "============================================================"
echo " 后端 API : http://127.0.0.1:8000"
echo " Swagger  : http://127.0.0.1:8000/docs"
echo " 前端页面 : http://127.0.0.1:5173"
echo " 健康检查 : curl http://127.0.0.1:8000/health/live"
echo "------------------------------------------------------------"
echo " 日志: 后端 /tmp/stb-backend.log   前端 /tmp/stb-frontend.log"
echo " 停止: pkill -f 'uvicorn app.main' ; pkill -f vite"
echo "============================================================"
