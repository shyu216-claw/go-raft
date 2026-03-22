# Raft God View 运行指南

## ✅ 已完成步骤

1. **安装 Python gRPC 依赖**
   ```bash
   pip3 install --break-system-packages grpcio grpcio-tools
   ```

2. **编译 proto 文件生成 Python gRPC 代码**
   ```bash
   cd /home/gem/workspace/agent/workspace/go-raft
   python3 -m grpc_tools.protoc -I. --python_out=tests/raft --grpc_python_out=tests/raft raft.proto
   ```
   
   生成的文件：
   - `tests/raft/raft_pb2.py`
   - `tests/raft/raft_pb2_grpc.py`

3. **验证 gRPC 模块加载**
   ```bash
   python3 -c "import grpc; import sys; sys.path.insert(0, 'tests/raft'); import raft_pb2; import raft_pb2_grpc; print('✅ Success')"
   ```

## ⚠️ 需要完成的步骤

### 1. 安装 Go 语言环境

项目需要 Go 来编译 Raft 节点二进制文件。

**选项 A: 使用 apt 安装（需要 sudo）**
```bash
sudo apt-get update
sudo apt-get install -y golang-go
```

**选项 B: 手动下载安装（无需 sudo）**
```bash
cd /tmp
curl -LO https://go.dev/dl/go1.21.0.linux-amd64.tar.gz
sudo tar -C /usr/local -xzf go1.21.0.linux-amd64.tar.gz
export PATH=$PATH:/usr/local/go/bin
```

**选项 C: 使用预编译的二进制文件**
如果你已经有编译好的 `raftrunner` 二进制文件，将其放到：
```
/home/gem/workspace/agent/workspace/go-raft/bin/raftrunner
```

### 2. 编译 Go Raft 节点

安装 Go 后，运行：
```bash
cd /home/gem/workspace/agent/workspace/go-raft/yourCode
sh compile.sh
```

这会在 `bin/` 目录下生成 `raftrunner` 可执行文件。

### 3. 启动 God View

**方式 A: 自动模式（推荐）**
```bash
cd /home/gem/workspace/agent/workspace/go-raft
python3 god_view.py
```
然后按 `Y` 自动启动 3 个 Raft 节点。

**方式 B: 手动模式**
```bash
# 终端 1: 启动节点 0
./yourCode/main 9000 "9000,9001,9002" 0 100 1000 &

# 终端 2: 启动节点 1
./yourCode/main 9001 "9000,9001,9002" 1 100 1000 &

# 终端 3: 启动节点 2
./yourCode/main 9002 "9000,9001,9002" 2 100 1000 &

# 终端 4: 启动 God View
python3 god_view.py
```

访问 http://localhost:5000 查看可视化界面。

## 🎯 当前状态总结

| 组件 | 状态 | 说明 |
|------|------|------|
| Python gRPC | ✅ 已安装 | grpcio 1.78.0 |
| Proto 编译 | ✅ 已完成 | 生成了 raft_pb2.py 和 raft_pb2_grpc.py |
| Flask | ✅ 已安装 | 3.1.3 |
| Go 语言 | ❌ 未安装 | 需要安装才能编译 Raft 节点 |
| Raft 节点二进制 | ❌ 未编译 | 需要先安装 Go |
| God View Web UI | ✅ 可运行 | 但无法自动启动节点（缺少二进制） |

## 📝 下一步建议

1. **如果只需要测试 God View UI**：
   - 手动启动几个 mock 服务器或使用现有的 Raft 节点
   - 访问 http://localhost:5000 查看界面

2. **如果需要完整运行 Raft 集群**：
   - 先安装 Go（参考上面的选项）
   - 编译 Raft 节点：`cd yourCode && sh compile.sh`
   - 运行 `python3 god_view.py` 并选择自动启动

3. **如果想运行官方测试**：
   - 安装 Go
   - 运行：`./scripts/rafttest.sh`

## 🔧 故障排查

**问题：找不到 protoc**
- 解决：使用 Python 内置的 grpc_tools，不需要单独安装 protoc

**问题：导入错误 `No module named 'raft_pb2'`**
- 解决：确保在 tests/raft 目录下有 raft_pb2.py 文件
- 或者重新运行 proto 编译命令

**问题：连接被拒绝**
- 检查 Raft 节点是否在运行
- 确认端口没有被防火墙阻止
- 检查 god_view.py 中配置的端口是否正确
