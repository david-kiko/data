# Dameng API

这是一个基于Spring Boot的达梦数据库API服务，提供SQL执行功能。

## 功能特性

- 提供REST API接口执行SQL语句
- 支持达梦数据库连接
- Docker容器化部署
- Swagger API文档支持

## 环境要求

- JDK 11+
- Maven 3.8+
- Docker

## 项目构建

1. 克隆项目到本地
2. 在项目根目录执行：
```bash
mvn clean package
```

## Docker构建和运行

1. 构建Docker镜像：
```bash
docker build -t dameng-api:1.0 .
```

2. 运行容器：
```bash
docker run -d -p 18085:18085 -e SPRING_DATASOURCE_URL=jdbc:dm://192.168.30.213:5236 -e SPRING_DATASOURCE_USERNAME=SYSDBA -e SPRING_DATASOURCE_PASSWORD=dameng12345 dameng-api:1.0
```

```
docker run -d -p 18086:18085 -e SPRING_DATASOURCE_URL=jdbc:dm://192.168.30.68:5236 -e SPRING_DATASOURCE_USERNAME=KMMOM -e SPRING_DATASOURCE_PASSWORD=Km123456789 192.168.30.232:5000/dameng-api:v2
```

## API文档

访问Swagger UI查看API文档：
```
http://localhost:18085/swagger-ui/index.html
```

## API使用说明

### 执行SQL

- 请求方式：POST
- 接口地址：/api/sql/execute
- Content-Type: application/json
- 请求体格式：
```json
{
    "sql": "SELECT * FROM your_table"
}
```
- 响应：查询结果列表

示例：
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT * FROM your_table"}' \
  http://localhost:18085/api/sql/execute
```

## 环境变量配置

| 环境变量 | 描述 | 默认值 |
|---------|------|--------|
| SPRING_DATASOURCE_URL | 达梦数据库连接URL | jdbc:dm://localhost:5236 |
| SPRING_DATASOURCE_USERNAME | 数据库用户名 | SYSDBA |
| SPRING_DATASOURCE_PASSWORD | 数据库密码 | SYSDBA |

## 注意事项

1. 请确保达梦数据库已正确安装并运行
2. 根据实际环境修改数据库连接配置
3. 生产环境部署时请注意修改默认密码
4. API文档访问地址为 http://localhost:18085/swagger-ui/index.html 