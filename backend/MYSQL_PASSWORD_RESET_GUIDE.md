# MySQL密码重置指南

## 问题
数据库连接失败：`Access denied for user 'root'@'localhost' (using password: YES)`

当前配置的密码：`361615`

## 解决方案

### 方案1: 使用MySQL Workbench重置密码（最简单）

1. 打开 MySQL Workbench
2. 点击 "Server" → "Users and Privileges"
3. 选择 `root@localhost` 用户
4. 点击 "Change Password"
5. 输入新密码：`361615`
6. 点击 "Apply"

### 方案2: 使用命令行重置密码

#### 步骤1: 停止MySQL服务
```powershell
Stop-Service MySQL97
```

#### 步骤2: 以安全模式启动MySQL（跳过权限验证）
```powershell
# 找到MySQL安装目录（通常在）
cd "C:\Program Files\MySQL\MySQL Server 9.7\bin"

# 或者
cd "C:\ProgramData\MySQL\MySQL Server 9.7\bin"

# 以安全模式启动
mysqld --skip-grant-tables --skip-networking
```

#### 步骤3: 在新的PowerShell窗口中连接MySQL
```powershell
mysql -u root
```

#### 步骤4: 重置密码
```sql
USE mysql;
ALTER USER 'root'@'localhost' IDENTIFIED BY '361615';
FLUSH PRIVILEGES;
EXIT;
```

#### 步骤5: 重启MySQL服务
```powershell
# 停止安全模式的MySQL（Ctrl+C）
# 然后正常启动服务
Start-Service MySQL97
```

### 方案3: 查找当前密码

如果你之前设置过密码但忘记了，可以尝试：

1. 检查MySQL配置文件
   - `C:\ProgramData\MySQL\MySQL Server 9.7\my.ini`
   - 查找是否有密码提示

2. 检查其他应用的配置文件
   - 如果你有其他应用连接到这个MySQL，检查它们的配置

3. 尝试常见密码
   - 空密码（直接回车）
   - `root`
   - `123456`
   - `password`

### 方案4: 使用空密码（如果MySQL允许）

尝试将 `.env` 文件中的密码设置为空：
```env
DB_PASSWORD=
```

然后测试连接：
```powershell
mysql -u root
```

## 测试新密码

重置密码后，运行测试脚本验证：
```powershell
python backend/test_db_connection.py
```

## 更新 .env 文件

确认密码正确后，更新 `backend/.env` 文件：
```env
DB_PASSWORD=你的正确密码
```

## 快速测试命令

```powershell
# 测试连接（会提示输入密码）
mysql -u root -p

# 如果成功，你会看到：
# mysql>

# 然后可以运行：
SHOW DATABASES;
```
