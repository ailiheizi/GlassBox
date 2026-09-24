# Bash 工具使用最佳实践

> ## 适用范围（先读这一段）
>
> 本文讨论的是**一次性、无状态 bash 调用**（每次调用是独立 shell 进程，只有工作目录保留）的使用技巧。
>
> 沙箱当前还提供**基于 tmux 的持久化会话**，与本文前提不同：`sandbox_bash_execute` 在同一 tmux 会话中执行，**工作目录与环境变量都会保留**；配套 `sandbox_bash_cwd`（查询当前目录）与 `sandbox_bash_env`（设置/读取环境变量），由沙箱 Agent 的 `/bash/*` 端点实现（`sandbox/tools/bash_session.py`）。
>
> 因此：
> - 需要在沙箱内跨多次调用保持 `cd` / `export` 时，**优先使用 `sandbox_bash_execute` + `sandbox_bash_env`**，不必像本文示例那样绕道写脚本文件或临时文件；
> - 本文技巧（合并命令、写脚本、一次性获取 token 并复用）仍适用于无持久会话的场景，例如调用方自身的一次性 bash 工具。

## 问题：为什么之前的做法"蠢"？

### ❌ 错误示例（之前的做法）

```bash
# 第一次调用 - 获取 Token
RANDOM_USER="test_user_1770058176_846"
TOKEN=$(curl -s ... | grep -o '"token":"[^"]*' | cut -d'"' -f4)
USER_ID="d97d1608-d45a-4323-b76c-6e28d4496c5d"

# 第二次调用 - 又要重新获取 Token！
RANDOM_USER="test_user_1770058176_846"
TOKEN=$(curl -s ... | grep -o '"token":"[^"]*' | cut -d'"' -f4)  # 重复！
curl -X GET "..." -H "Authorization: Bearer $TOKEN"

# 第三次调用 - 还是要重新获取！
RANDOM_USER="test_user_1770058176_846"
TOKEN=$(curl -s ... | grep -o '"token":"[^"]*' | cut -d'"' -f4)  # 又重复！
curl -X POST "..." -H "Authorization: Bearer $TOKEN"
```

**问题**：
1. 每次都重新登录获取 Token（浪费 API 调用）
2. 重复的代码（维护困难）
3. 效率低下（每次都要等待登录响应）
4. 看起来很"蠢"（明明已经有了 Token，为什么还要重新获取？）

---

## 原因：Bash 工具的工作原理

### Claude Code 的 Bash 工具特性

根据文档：
> Working directory persists between commands; shell state (everything else) does not.

这意味着：
- ✅ **工作目录会保持** - `cd /some/path` 后，下次调用仍在该目录
- ❌ **环境变量不保持** - `export VAR=value` 后，下次调用时 VAR 不存在
- ❌ **Shell 变量不保持** - `TOKEN="xxx"` 后，下次调用时 TOKEN 不存在
- ❌ **函数不保持** - 定义的函数在下次调用时消失

### 为什么这样设计？

每次 Bash 工具调用都是一个**独立的 shell 进程**：
```
调用 1: bash -c "TOKEN=xxx; echo $TOKEN"  # 进程 1234
调用 2: bash -c "echo $TOKEN"             # 进程 5678（新进程，没有 TOKEN）
```

---

## ✅ 正确做法

### 方案 1: 在单个 Bash 调用中完成所有步骤（推荐）

```bash
#!/bin/bash

# 1. 获取 Token（只执行一次）
TOKEN=$(curl -s ... | grep -o '"token":"[^"]*' | cut -d'"' -f4)
USER_ID=$(curl -s ... | grep -o '"id":"[^"]*' | cut -d'"' -f4)

# 2. 使用 Token 执行多个操作
curl -X GET "..." -H "Authorization: Bearer $TOKEN"
curl -X POST "..." -H "Authorization: Bearer $TOKEN"
curl -X DELETE "..." -H "Authorization: Bearer $TOKEN"

# 3. 清理
echo "完成"
```

**优势**：
- ✅ Token 只获取一次
- ✅ 所有变量在整个脚本中可用
- ✅ 代码简洁，易于维护
- ✅ 执行效率高

### 方案 2: 使用临时文件保存状态

```bash
# 第一次调用 - 保存 Token
TOKEN=$(curl -s ... | grep -o '"token":"[^"]*' | cut -d'"' -f4)
echo "$TOKEN" > /tmp/test_token.txt
echo "$USER_ID" > /tmp/test_user_id.txt

# 后续调用 - 读取 Token
TOKEN=$(cat /tmp/test_token.txt)
USER_ID=$(cat /tmp/test_user_id.txt)
curl -X GET "..." -H "Authorization: Bearer $TOKEN"

# 清理
rm -f /tmp/test_token.txt /tmp/test_user_id.txt
```

**优势**：
- ✅ 可以跨多个 Bash 调用保持状态
- ✅ 适合需要分步执行的场景

**劣势**：
- ⚠️ 需要手动管理临时文件
- ⚠️ 需要清理临时文件

### 方案 3: 使用 `&&` 链接命令

```bash
# 简单的顺序操作
cd /some/path && \
  git add . && \
  git commit -m "message" && \
  git push
```

**适用场景**：
- 命令之间有依赖关系
- 需要在前一个命令成功后才执行下一个
- 不需要复杂的变量传递

---

## 📋 最佳实践

### 1. 优先使用单个脚本文件

**推荐**：
```bash
# 创建脚本文件
cat > test_script.sh << 'EOF'
#!/bin/bash
TOKEN=$(get_token)
do_something_with_token "$TOKEN"
do_another_thing "$TOKEN"
EOF

# 执行脚本
bash test_script.sh
```

**不推荐**：
```bash
# 多次调用，每次都重新获取
bash -c "TOKEN=$(get_token); do_something"
bash -c "TOKEN=$(get_token); do_another"  # 重复获取！
```

### 2. 合理使用命令链接

**使用 `&&`**（前一个成功才执行下一个）：
```bash
mkdir -p build && cd build && cmake .. && make
```

**使用 `;`**（无论成功失败都继续）：
```bash
echo "Starting..."; run_command; echo "Done"
```

### 3. 避免不必要的分割

**不好**：
```bash
# 调用 1
cd /project

# 调用 2
ls -la

# 调用 3
cat file.txt
```

**更好**：
```bash
cd /project && ls -la && cat file.txt
```

**最好**（如果逻辑复杂）：
```bash
#!/bin/bash
cd /project
ls -la
cat file.txt
# ... 更多操作
```

### 4. 何时应该分开调用

**应该分开的情况**：
1. **需要查看中间结果再决定下一步**
   ```bash
   # 调用 1: 检查状态
   git status

   # 根据结果决定是否继续
   # 调用 2: 提交
   git commit -m "message"
   ```

2. **操作之间需要等待或用户确认**
   ```bash
   # 调用 1: 启动服务
   docker-compose up -d

   # 等待服务启动...

   # 调用 2: 测试服务
   curl http://localhost:8080/health
   ```

3. **独立的、不相关的操作**
   ```bash
   # 调用 1: 检查 Go 服务
   cd gateway && go test ./...

   # 调用 2: 检查 Python 服务
   cd services/ai-service && pytest
   ```

---

## 🎯 实际案例对比

### 案例：完整的 API 测试流程

#### ❌ 低效做法（之前）

```bash
# 步骤 1: 注册用户
RANDOM_USER="test_user_$(date +%s)"
curl -X POST .../register -d "{\"username\":\"$RANDOM_USER\",...}"

# 步骤 2: 登录（重新定义变量）
RANDOM_USER="test_user_1770058176"  # 硬编码！
TOKEN=$(curl -X POST .../login ...)

# 步骤 3: 获取数据（又重新登录）
RANDOM_USER="test_user_1770058176"  # 又硬编码！
TOKEN=$(curl -X POST .../login ...)  # 又登录！
curl -X GET .../data -H "Authorization: Bearer $TOKEN"

# 步骤 4: 创建资源（还是重新登录）
RANDOM_USER="test_user_1770058176"  # 还是硬编码！
TOKEN=$(curl -X POST .../login ...)  # 还是登录！
curl -X POST .../resource -H "Authorization: Bearer $TOKEN"
```

**问题统计**：
- 登录次数：4 次（实际只需要 1 次）
- 硬编码次数：3 次（容易出错）
- 代码重复：严重

#### ✅ 高效做法（改进后）

```bash
#!/bin/bash

# 1. 初始化
RANDOM_USER="test_user_$(date +%s)_$$"
echo "测试用户: $RANDOM_USER"

# 2. 注册
curl -X POST .../register -d "{\"username\":\"$RANDOM_USER\",...}"

# 3. 登录（只执行一次）
LOGIN_RESPONSE=$(curl -X POST .../login ...)
TOKEN=$(echo "$LOGIN_RESPONSE" | grep -o '"token":"[^"]*' | cut -d'"' -f4)
USER_ID=$(echo "$LOGIN_RESPONSE" | grep -o '"id":"[^"]*' | cut -d'"' -f4)

echo "Token: ${TOKEN:0:30}..."
echo "User ID: $USER_ID"

# 4. 使用 Token 执行多个操作
curl -X GET .../data -H "Authorization: Bearer $TOKEN"
curl -X POST .../resource -H "Authorization: Bearer $TOKEN"
curl -X PUT .../update -H "Authorization: Bearer $TOKEN"
curl -X DELETE .../cleanup -H "Authorization: Bearer $TOKEN"

# 5. 清理
echo "测试完成"
```

**改进统计**：
- 登录次数：1 次（减少 75%）
- 硬编码次数：0 次
- 代码重复：无
- 执行时间：减少约 60%

---

## 📊 性能对比

### 测试场景：完整的 API 测试流程

| 指标 | 低效做法 | 高效做法 | 改进 |
|------|---------|---------|------|
| Bash 调用次数 | 7 次 | 1 次 | -86% |
| 登录 API 调用 | 4 次 | 1 次 | -75% |
| 总执行时间 | ~8 秒 | ~3 秒 | -62% |
| 代码行数 | ~50 行 | ~30 行 | -40% |
| 维护难度 | 高 | 低 | ✅ |

---

## 🔧 实用工具函数

### 创建可复用的测试脚本

```bash
#!/bin/bash
# test_utils.sh - 可复用的测试工具函数

# 颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# 登录并获取 Token
login() {
    local username=$1
    local password=$2

    local response=$(curl -s -X POST "http://localhost:8080/api/v1/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"username\":\"$username\",\"password\":\"$password\"}")

    TOKEN=$(echo "$response" | grep -o '"token":"[^"]*' | cut -d'"' -f4)
    USER_ID=$(echo "$response" | grep -o '"id":"[^"]*' | head -1 | cut -d'"' -f4)

    if [ -n "$TOKEN" ]; then
        success "登录成功 (User ID: $USER_ID)"
        return 0
    else
        error "登录失败"
        return 1
    fi
}

# 使用示例
main() {
    # 登录一次
    login "testuser" "password123" || exit 1

    # 使用 Token 执行多个操作
    curl -X GET "..." -H "Authorization: Bearer $TOKEN"
    curl -X POST "..." -H "Authorization: Bearer $TOKEN"

    success "测试完成"
}

main
```

---

## 📝 总结

### 核心原则

1. **一次获取，多次使用** - 避免重复获取相同的数据
2. **合并相关操作** - 将相关的命令放在同一个脚本中
3. **使用脚本文件** - 复杂逻辑写成脚本，而不是多次调用
4. **保持状态** - 在单个会话中保持变量和状态

### 记住

- ✅ Bash 工具的工作目录会保持
- ❌ Bash 工具的变量和状态不会保持
- ✅ 使用单个脚本文件来保持状态
- ✅ 使用临时文件来跨调用保存数据
- ✅ 合理使用 `&&` 和 `;` 链接命令

### 何时使用哪种方式

| 场景 | 推荐方式 | 原因 |
|------|---------|------|
| 简单的顺序操作 | `&&` 链接 | 简洁高效 |
| 复杂的测试流程 | 脚本文件 | 易于维护 |
| 需要查看中间结果 | 分开调用 | 便于调试 |
| 独立的操作 | 分开调用 | 逻辑清晰 |
| 需要保持状态 | 脚本文件或临时文件 | 避免重复 |

---

## 🎓 学到的教训

1. **不要盲目重复** - 如果发现自己在重复相同的代码，说明方法有问题
2. **理解工具特性** - 了解 Bash 工具的工作原理，才能正确使用
3. **优化执行效率** - 减少不必要的 API 调用和重复操作
4. **保持代码简洁** - 好的代码应该简洁、高效、易于维护

### 之前的做法为什么"蠢"？

因为它违反了这些原则：
- ❌ 重复获取相同的数据（Token）
- ❌ 硬编码变量值（容易出错）
- ❌ 浪费 API 调用（效率低下）
- ❌ 代码重复（维护困难）

### 改进后的做法为什么"聪明"？

因为它遵循了这些原则：
- ✅ 一次获取，多次使用
- ✅ 变量自动传递（无需硬编码）
- ✅ 最小化 API 调用
- ✅ 代码简洁易维护

---

**记住**：好的代码不仅要能工作，还要高效、简洁、易于维护。
