# 管理员功能说明文档

## 概述

本文档介绍了 Transhub Backend 新增的管理员功能，包括基于角色的访问控制(RBAC)系统、管理员 API 接口和使用方法。

## 功能特性

### 1. 角色系统

系统支持三种用户角色：

- **student**: 普通学生用户（默认角色）
- **admin**: 管理员，可以管理学生用户和查看统计信息
- **super_admin**: 超级管理员，拥有所有权限

### 2. 权限控制

- 管理员可以：

  - 查看和管理用户列表
  - 查看任务列表和统计信息
  - 锁定/解锁用户账户

- 超级管理员额外可以：
  - 管理其他管理员账户
  - 查看系统信息
  - 更改任何用户的角色

### 3. 安全特性

- 角色权限验证装饰器
- 防止管理员锁定自己
- 只有超级管理员可以修改管理员用户
- JWT token 包含角色信息

## API 接口

### 用户管理

#### 获取用户列表

```
GET /admin/users?page=1&size=20&keyword=&role=&active=&deleted=
```

查询参数：

- `page`: 页码（默认 1）
- `size`: 每页大小（默认 20，最大 100）
- `keyword`: 搜索关键词（用户名、真实姓名、学号）
- `role`: 角色筛选（student/admin/super_admin）
- `active`: 活跃状态筛选（true/false）
- `deleted`: 删除状态筛选（true=已删除，false=未删除，不传=默认未删除）

#### 更新用户信息

```
POST /admin/users/update
Content-Type: application/json

{
    "user_id": "用户ID",
    "role": "新角色（可选）",
    "is_locked": true/false（可选）
}
```

安全说明：

- 只有超级管理员可以修改其他管理员用户
- 只有超级管理员可以更改任何用户的角色
- 不能锁定自己的账户

#### 重置用户密码

```
POST /admin/users/reset_password
Content-Type: application/json

{
    "user_id": "用户ID",
    "new_password": "新密码（可选，默认为123456）"
}
```

安全说明：

- 只有管理员可以重置学生用户密码
- 只有超级管理员可以重置管理员用户密码
- 不能重置自己的密码
- 默认重置密码为 "123456"

#### 软删除用户

```
POST /admin/users/delete
Content-Type: application/json

{
    "user_id": "用户ID"
}
```

#### 恢复被删除的用户

```
POST /admin/users/restore
Content-Type: application/json

{
    "user_id": "用户ID"
}
```

安全说明：

- 软删除不会真正删除数据库记录，只是标记为已删除
- 被删除的用户无法登录系统
- 只有管理员可以删除学生用户
- 只有超级管理员可以删除管理员用户
- 不能删除自己的账户
- 被删除的用户可以被恢复
- 要查看已删除的用户，使用用户列表接口并设置 `deleted=true` 参数

## 软删除机制详解

### 设计原理

软删除是一种数据安全策略，通过在数据库中添加标记字段（`is_deleted` 和 `deleted_at`）来标识已删除的记录，而不是物理删除数据库行。这种设计有以下优势：

1. **数据安全**：避免误删除导致的数据丢失
2. **可审计性**：保留完整的用户操作历史
3. **可恢复性**：被删除的用户可以随时恢复
4. **关联完整性**：保持用户相关数据（任务、成绩等）的完整性

### 实现细节

- `is_deleted`: 布尔字段，标识用户是否被删除
- `deleted_at`: 时间戳字段，记录删除操作的时间
- 默认查询会自动过滤已删除用户
- 管理员可通过 `deleted=true` 参数查看已删除用户

### 影响范围

软删除会影响以下功能：

1. **用户登录**：已删除用户无法登录
2. **用户查询**：默认不显示已删除用户
3. **数据统计**：统计数据会区分活跃用户和已删除用户
4. **关联查询**：相关任务和成绩数据仍然保留

### 任务管理

#### 获取任务列表

```
GET /admin/tasks?page=1&size=20&user_id=&status=&cname=
```

查询参数：

- `page`: 页码
- `size`: 每页大小
- `user_id`: 用户 ID 筛选
- `status`: 状态筛选
- `cname`: 比赛名称筛选

### 统计信息

#### 获取系统统计

```
GET /admin/stats?date_from=&date_to=&cname=
```

返回：

- 用户总数、活跃用户数、任务总数
- 任务状态统计
- 比赛参与统计
- 角色分布统计

#### 获取系统信息（仅超级管理员）

```
GET /admin/system/info
```

返回系统资源使用情况和配置信息。

## 部署指南

### 1. 环境变量配置

在 `.env.development` 或 `.env.production` 文件中添加：

```bash
# 超级管理员配置
SUPER_ADMIN_USERNAME=admin
SUPER_ADMIN_PASSWORD=your_secure_password
SUPER_ADMIN_REAL_NAME=系统管理员
SUPER_ADMIN_SNO=ADMIN001
```

### 2. 数据库迁移

执行以下命令为现有数据库添加必要字段：

```bash
python migrate_admin.py
```

### 3. 创建超级管理员

```bash
python init_admin.py
```

### 4. 重启应用

重启应用以加载新的管理员功能。

## 使用示例

### 1. 管理员登录

管理员使用普通登录接口，系统会自动识别角色：

```bash
curl -X POST http://localhost:5000/user_login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin123",
    "cname": "任意课程名"
  }'
```

登录成功后，JWT token 中会包含角色信息。

### 2. 获取用户列表

```bash
curl -X GET "http://localhost:5000/admin/users?page=1&size=10" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### 3. 锁定用户

```bash
curl -X POST http://localhost:5000/admin/users/update \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "user_id": "user_id_here",
    "is_locked": true
  }'
```

### 4. 提升用户为管理员（仅超级管理员）

```bash
curl -X POST http://localhost:5000/admin/users/update \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_SUPER_ADMIN_JWT_TOKEN" \
  -d '{
    "user_id": "user_id_here",
    "role": "admin"
  }'
```

### 5. 重置用户密码

```bash
curl -X POST http://localhost:5000/admin/users/reset_password \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "user_id": "user_id_here",
    "new_password": "123456"
  }'
```

### 6. 软删除用户

```bash
curl -X POST http://localhost:5000/admin/users/delete \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "user_id": "user_id_here"
  }'
```

### 7. 恢复被删除的用户

```bash
curl -X POST http://localhost:5000/admin/users/restore \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "user_id": "user_id_here"
  }'
```

### 8. 查看已删除的用户

```bash
curl -X GET "http://localhost:5000/admin/users?page=1&size=10&deleted=true" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## 前端集成

### 1. 角色检查

从 JWT token 中获取用户角色：

```javascript
// 假设你有获取JWT payload的方法
const userRole = getJWTPayload().role;

// 检查是否为管理员
const isAdmin = ["admin", "super_admin"].includes(userRole);
const isSuperAdmin = userRole === "super_admin";
```

### 2. 条件渲染

根据用户角色显示不同的界面元素：

```javascript
// React示例
{
	isAdmin && (
		<AdminPanel>
			<UserManagement />
			<TaskMonitoring />
			<Statistics />
		</AdminPanel>
	);
}

{
	isSuperAdmin && (
		<SuperAdminPanel>
			<SystemInfo />
			<AdminManagement />
		</SuperAdminPanel>
	);
}
```

## 安全注意事项

1. **强密码策略**: 为超级管理员设置强密码
2. **定期审计**: 定期检查管理员操作日志
3. **最小权限原则**: 仅在必要时授予管理员权限
4. **环境变量保护**: 确保环境变量文件不被提交到版本控制
5. **HTTPS**: 生产环境务必使用 HTTPS
6. **JWT 安全**: 设置合适的 JWT 过期时间

## 故障排除

### 1. 数据库迁移失败

如果迁移脚本失败，可以手动执行 SQL：

```sql
ALTER TABLE student ADD COLUMN role VARCHAR(20) DEFAULT 'student';
ALTER TABLE student ADD COLUMN is_locked BOOLEAN DEFAULT FALSE;
UPDATE student SET role = 'student' WHERE role IS NULL OR role = '';
UPDATE student SET is_locked = FALSE WHERE is_locked IS NULL;
```

### 2. 超级管理员无法登录

检查：

1. 环境变量是否正确设置
2. 数据库中用户是否存在
3. 角色是否为 'super_admin'
4. 账户是否被锁定

### 3. 权限验证失败

确保：

1. JWT token 有效且包含角色信息
2. 用户角色正确
3. 装饰器正确应用到 API 端点

## 更新日志

### v1.0.0 (2024-06-28)

- 初始版本
- 添加角色系统（student/admin/super_admin）
- 实现用户管理、任务监控、统计功能
- 添加权限控制装饰器
- 提供数据库迁移和初始化脚本

## 贡献指南

如果需要扩展管理员功能，请：

1. 在 `UserRole` 枚举中添加新角色
2. 更新权限装饰器逻辑
3. 添加相应的 API 端点
4. 更新验证模式
5. 编写测试用例
6. 更新文档

## 支持

如有问题，请：

1. 检查日志文件中的错误信息
2. 验证配置是否正确
3. 查看本文档的故障排除部分
4. 联系开发团队

## 角色更改权限详解

### 权限矩阵

| 操作者角色  | 目标用户角色 | 锁定/解锁 | 角色更改 |
| ----------- | ------------ | --------- | -------- |
| admin       | student      | ✅        | ❌       |
| admin       | admin        | ❌        | ❌       |
| admin       | super_admin  | ❌        | ❌       |
| super_admin | student      | ✅        | ✅       |
| super_admin | admin        | ✅        | ✅       |
| super_admin | super_admin  | ✅        | ✅       |

### 权限检查流程

1. **基础权限**：需要管理员或以上权限
2. **目标用户检查**：验证目标用户存在
3. **管理员保护**：普通管理员不能操作其他管理员
4. **自我保护**：不能锁定自己的账户
5. **角色更改权限**：只有超级管理员可以更改角色

### 示例场景

#### 场景 1：普通管理员尝试更改学生角色

```bash
# 请求（会失败）
curl -X POST http://localhost:5000/admin/users/update \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -d '{"user_id": "student_id", "role": "admin"}'

# 响应
{
  "code": 403,
  "message": "只有超级管理员可以更改用户角色"
}
```

#### 场景 2：超级管理员提升学生为管理员

```bash
# 请求（会成功）
curl -X POST http://localhost:5000/admin/users/update \
  -H "Authorization: Bearer SUPER_ADMIN_TOKEN" \
  -d '{"user_id": "student_id", "role": "admin"}'

# 响应
{
  "code": 200,
  "message": "用户信息更新成功"
}
```

#### 场景 3：普通管理员锁定学生账户

```bash
# 请求（会成功）
curl -X POST http://localhost:5000/admin/users/update \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -d '{"user_id": "student_id", "is_locked": true}'

# 响应
{
  "code": 200,
  "message": "用户信息更新成功"
}
```
