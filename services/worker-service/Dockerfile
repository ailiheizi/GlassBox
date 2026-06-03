# Build stage
FROM golang:1.24-alpine AS builder

WORKDIR /app

# 安装依赖
COPY go.mod go.sum ./
RUN GOPROXY=https://goproxy.cn,direct go mod download

# 复制源代码
COPY . .

# 编译
RUN GOPROXY=https://goproxy.cn,direct CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o worker ./cmd/worker

# Runtime stage
FROM alpine:latest

RUN apk --no-cache add ca-certificates

WORKDIR /root/

# 复制编译好的二进制文件
COPY --from=builder /app/worker .

# 暴露端口
EXPOSE 9000

# 运行
CMD ["./worker"]
