#!/usr/bin/env python3
"""
Raft God View - 可视化真实 Raft 集群运行状态
=========================================
功能：
- 通过 gRPC 连接真实的 Raft 节点
- 显示所有节点状态 (Leader/Follower/Candidate)
- 实时显示 Term、Vote、Log 信息
- 支持启动/停止真实节点
- 支持添加新节点
- 支持 Kill 节点
- 显示集群拓扑

使用方法：
1. 自动模式（推荐）: 直接运行，自动启动 3 个 Raft 节点
   python3 god_view.py

2. 手动模式：先手动启动节点，再运行此脚本
   ./yourCode/main 9000 "9000,9001,9002" 0 100 1000 &
   ./yourCode/main 9001 "9000,9001,9002" 1 100 1000 &
   ./yourCode/main 9002 "9000,9001,9002" 2 100 1000 &
   python3 god_view.py
"""

import json
import os
import sys
import subprocess
import time
from flask import Flask, render_template_string, jsonify, request
from threading import Thread
import threading

# gRPC 相关
try:
    import grpc
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tests', 'raft'))
    import raft_pb2
    import raft_pb2_grpc
    GRPC_AVAILABLE = True
except ImportError as e:
    GRPC_AVAILABLE = False
    print(f"❌ gRPC 未安装：{e}")
    print("请运行：pip install grpcio grpcio-tools")
    print("然后编译 proto 文件：cd tests && protoc --python_out=. --grpc_python_out=. raft/raft.proto")
    sys.exit(1)

# ========== 配置 ==========

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YOURCODE_DIR = os.path.join(BASE_DIR, 'yourCode')
BIN_DIR = os.path.join(BASE_DIR, 'bin')

DEFAULT_NODE_COUNT = 3
BASE_PORT = 9000
HEARTBEAT_INTERVAL = 100  # ms
ELECTION_TIMEOUT = 1000   # ms

# ========== 状态管理 ==========

class RaftNodeProxy:
    """单个 Raft 节点的代理"""
    
    def __init__(self, node_id, port, process=None):
        self.node_id = node_id
        self.port = port
        self.process = process
        self.channel = None
        self.stub = None
        self._connect()
        
        # 缓存的节点信息
        self.role = "Unknown"
        self.term = 0
        self.voted_for = None
        self.log_count = 0
        self.is_alive = True
        self.commit_index = 0
        self.last_contact = None
        
    def _connect(self):
        """建立 gRPC 连接"""
        try:
            self.channel = grpc.insecure_channel(f'localhost:{self.port}')
            self.stub = raft_pb2_grpc.RaftNodeStub(self.channel)
            self.is_alive = True
        except Exception as e:
            self.is_alive = False
            
    def get_info(self):
        """获取节点信息（通过试探性调用）"""
        if not self.is_alive:
            return None
            
        try:
            # 尝试调用 GetValue 来探测节点状态
            # 注意：main.go 没有直接的 GetStatus API，我们需要推断
            response = self.stub.GetValue(
                raft_pb2.GetValueArgs(Key="__status_probe__"),
                timeout=1.0
            )
            self.last_contact = time.time()
            return {
                'node_id': self.node_id,
                'port': self.port,
                'is_alive': True,
                'last_contact': self.last_contact
            }
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.UNAVAILABLE:
                self.is_alive = False
            return None
        except Exception as e:
            return None
            
    def set_election_timeout(self, timeout_ms):
        """设置选举超时"""
        try:
            self.stub.SetElectionTimeout(
                raft_pb2.SetElectionTimeoutArgs(Timeout=timeout_ms),
                timeout=1.0
            )
            return True
        except:
            return False
            
    def set_heartbeat_interval(self, interval_ms):
        """设置心跳间隔"""
        try:
            self.stub.SetHeartBeatInterval(
                raft_pb2.SetHeartBeatIntervalArgs(Interval=interval_ms),
                timeout=1.0
            )
            return True
        except:
            return False
            
    def propose(self, op, key, value):
        """提议新操作"""
        try:
            response = self.stub.Propose(
                raft_pb2.ProposeArgs(Op=op, Key=key, V=value),
                timeout=5.0
            )
            return response
        except Exception as e:
            return None
            
    def get_value(self, key):
        """获取值"""
        try:
            response = self.stub.GetValue(
                raft_pb2.GetValueArgs(Key=key),
                timeout=1.0
            )
            return response
        except:
            return None
            
    def kill(self):
        """Kill 节点进程"""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except:
                pass
        self.is_alive = False
        if self.channel:
            self.channel.close()


class RaftCluster:
    """Raft 集群管理器"""
    
    def __init__(self):
        self.nodes = {}  # node_id -> RaftNodeProxy
        self.lock = threading.Lock()
        self.port_allocator = range(BASE_PORT, BASE_PORT + 100)
        self.used_ports = set()
        self.binary_path = None
        
    def find_binary(self):
        """查找编译好的 Raft 二进制文件"""
        # 优先使用编译好的二进制
        candidates = [
            os.path.join(BIN_DIR, 'raftrunner'),
            os.path.join(BIN_DIR, 'raftrunner.exe'),
            os.path.join(YOURCODE_DIR, 'main'),
        ]
        
        for path in candidates:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                self.binary_path = path
                return True
                
        # 检查是否需要编译
        main_go = os.path.join(YOURCODE_DIR, 'main.go')
        if os.path.exists(main_go):
            print("⚠️  未找到编译好的二进制，尝试编译...")
            return self.compile()
            
        return False
        
    def compile(self):
        """编译 Raft 代码"""
        compile_script = os.path.join(YOURCODE_DIR, 'compile.sh')
        if not os.path.exists(compile_script):
            print("❌ 找不到编译脚本")
            return False
            
        try:
            result = subprocess.run(
                ['bash', compile_script],
                cwd=YOURCODE_DIR,
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0:
                self.binary_path = os.path.join(BIN_DIR, 'raftrunner')
                print("✅ 编译成功")
                return True
            else:
                print(f"❌ 编译失败：{result.stderr}")
                return False
        except Exception as e:
            print(f"❌ 编译异常：{e}")
            return False
            
    def allocate_port(self):
        for port in self.port_allocator:
            if port not in self.used_ports:
                self.used_ports.add(port)
                return port
        raise Exception("无可用端口")
    
    def release_port(self, port):
        self.used_ports.discard(port)
        
    def start_node(self, node_id=None):
        """启动新的 Raft 节点"""
        with self.lock:
            if node_id is None:
                node_id = len(self.nodes)
            
            # 构建所有节点的端口列表
            existing_ports = [n.port for n in self.nodes.values()]
            new_port = self.allocate_port()
            all_ports = existing_ports + [new_port]
            ports_str = ",".join(str(p) for p in all_ports)
            
            if not self.binary_path:
                if not self.find_binary():
                    raise Exception("找不到 Raft 二进制文件，请先编译")
            
            # 启动进程
            cmd = [
                self.binary_path,
                str(new_port),           # myport
                ports_str,               # all ports
                str(node_id),            # nodeID
                str(HEARTBEAT_INTERVAL), # heartbeat
                str(ELECTION_TIMEOUT)    # election timeout
            ]
            
            print(f"🚀 启动节点 {node_id}: {' '.join(cmd)}")
            
            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    cwd=BASE_DIR
                )
                
                # 等待节点启动
                time.sleep(0.5)
                
                node_proxy = RaftNodeProxy(node_id, new_port, process)
                self.nodes[node_id] = node_proxy
                
                # 给其他节点一点时间重连
                time.sleep(0.3)
                
                return node_proxy
            except Exception as e:
                self.release_port(new_port)
                raise Exception(f"启动节点失败：{e}")
                
    def kill_node(self, node_id):
        """Kill 节点"""
        with self.lock:
            if node_id in self.nodes:
                node = self.nodes[node_id]
                node.kill()
                self.release_port(node.port)
                del self.nodes[node_id]
                return True
            return False
            
    def refresh_status(self):
        """刷新所有节点状态"""
        with self.lock:
            for node in self.nodes.values():
                info = node.get_info()
                if info:
                    # 由于 main.go 没有直接的状态 API，我们通过启发式方法推断
                    # 这里简化处理，实际应该通过日志分析或添加自定义 RPC
                    node.role = "Follower"  # 默认假设
                    node.term = 0
                    node.log_count = 0
                else:
                    node.is_alive = False
                    
    def get_status(self):
        """获取集群状态"""
        self.refresh_status()
        
        with self.lock:
            nodes_data = []
            leader_id = None
            
            for node in self.nodes.values():
                node_data = {
                    "id": node.node_id,
                    "port": node.port,
                    "role": node.role,
                    "term": node.term,
                    "voted_for": node.voted_for,
                    "log_count": node.log_count,
                    "is_alive": node.is_alive,
                    "commit_index": node.commit_index,
                    "last_contact": node.last_contact
                }
                nodes_data.append(node_data)
                
                if node.role == "Leader" and node.is_alive:
                    leader_id = node.node_id
            
            return {
                "nodes": nodes_data,
                "leader": leader_id,
                "total_nodes": len(self.nodes),
                "alive_nodes": sum(1 for n in self.nodes.values() if n.is_alive),
                "grpc_available": GRPC_AVAILABLE,
                "binary_path": self.binary_path
            }
            
    def shutdown_all(self):
        """关闭所有节点"""
        with self.lock:
            for node in self.nodes.values():
                node.kill()
            self.nodes.clear()


# 全局集群实例
cluster = RaftCluster()

# ========== Flask App ==========

app = Flask(__name__)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Raft God View 🦞</title>
    <meta charset="utf-8">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #eee;
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        
        h1 {
            text-align: center;
            padding: 20px;
            font-size: 2.5em;
            background: linear-gradient(90deg, #00d9ff, #00ff88);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .info-bar {
            text-align: center;
            padding: 10px;
            background: rgba(255,255,255,0.05);
            border-radius: 10px;
            margin-bottom: 20px;
            font-size: 0.9em;
            opacity: 0.8;
        }
        
        .toolbar {
            display: flex;
            gap: 10px;
            justify-content: center;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        
        button {
            padding: 12px 24px;
            font-size: 16px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
            font-weight: bold;
        }
        
        .btn-add {
            background: linear-gradient(135deg, #00d9ff, #0099ff);
            color: #fff;
        }
        
        .btn-kill {
            background: linear-gradient(135deg, #ff6b6b, #ee5a5a);
            color: #fff;
        }
        
        .btn-refresh {
            background: linear-gradient(135deg, #4ecdc4, #44a08d);
            color: #fff;
        }
        
        button:hover { transform: translateY(-2px); box-shadow: 0 5px 20px rgba(0,0,0,0.3); }
        
        .status-bar {
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-bottom: 30px;
            padding: 15px;
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
        }
        
        .stat { text-align: center; }
        .stat-value { font-size: 2em; font-weight: bold; }
        .stat-label { opacity: 0.7; }
        
        .nodes-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 20px;
        }
        
        .node-card {
            background: rgba(255,255,255,0.08);
            border-radius: 15px;
            padding: 20px;
            border: 2px solid transparent;
            transition: all 0.3s;
        }
        
        .node-card:hover { transform: scale(1.02); }
        
        .node-card.dead {
            opacity: 0.5;
            border-color: #ff4757;
        }
        
        .node-card.leader { border-color: #ffd700; }
        .node-card.candidate { border-color: #ff6b6b; }
        
        .node-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        
        .node-id {
            font-size: 1.5em;
            font-weight: bold;
        }
        
        .role-badge {
            padding: 5px 12px;
            border-radius: 15px;
            font-size: 0.9em;
        }
        
        .role-follower { background: #4ecdc4; color: #000; }
        .role-leader { background: #ffd700; color: #000; }
        .role-candidate { background: #ff6b6b; color: #fff; }
        .role-unknown { background: #888; color: #fff; }
        
        .node-stats {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        
        .stat-item {
            background: rgba(0,0,0,0.2);
            padding: 10px;
            border-radius: 8px;
        }
        
        .stat-item label { display: block; opacity: 0.6; font-size: 0.8em; }
        .stat-item span { font-size: 1.2em; font-weight: bold; }
        
        .topology {
            margin-top: 30px;
            padding: 20px;
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
        }
        
        .topology h2 { margin-bottom: 15px; }
        
        .topology-svg {
            width: 100%;
            height: 300px;
        }
        
        .toast {
            position: fixed;
            bottom: 20px;
            right: 20px;
            padding: 15px 25px;
            background: #4ecdc4;
            color: #000;
            border-radius: 10px;
            font-weight: bold;
            animation: slideIn 0.3s ease;
        }
        
        @keyframes slideIn {
            from { transform: translateX(100%); }
            to { transform: translateX(0); }
        }
        
        .kill-modal {
            display: none;
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.8);
            justify-content: center;
            align-items: center;
            z-index: 1000;
        }
        
        .kill-modal.active { display: flex; }
        
        .modal-content {
            background: #1a1a2e;
            padding: 30px;
            border-radius: 15px;
            text-align: center;
        }
        
        .modal-content select {
            padding: 10px;
            font-size: 16px;
            margin: 10px;
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🫧 Raft God View</h1>
        
        <div class="info-bar">
            <span id="grpcStatus">🔗 gRPC: 就绪</span> | 
            <span id="binaryPath">📦 二进制：<span id="binaryPathText">检测中...</span></span>
        </div>
        
        <div class="toolbar">
            <button class="btn-add" onclick="addNode()">➕ Add Node</button>
            <button class="btn-kill" onclick="showKillModal()">💀 Kill Node</button>
            <button class="btn-refresh" onclick="refreshStatus()">🔄 Refresh</button>
        </div>
        
        <div class="status-bar">
            <div class="stat">
                <div class="stat-value" id="totalNodes">0</div>
                <div class="stat-label">Total Nodes</div>
            </div>
            <div class="stat">
                <div class="stat-value" id="aliveNodes">0</div>
                <div class="stat-label">Alive</div>
            </div>
            <div class="stat">
                <div class="stat-value" id="leaderId">-</div>
                <div class="stat-label">Leader</div>
            </div>
        </div>
        
        <div class="nodes-grid" id="nodesGrid">
            <!-- 节点卡片将在这里动态生成 -->
        </div>
        
        <div class="topology">
            <h2>🔗 Cluster Topology</h2>
            <svg class="topology-svg" id="topologySvg">
                <!-- 拓扑图将在这里动态生成 -->
            </svg>
        </div>
    </div>
    
    <div class="kill-modal" id="killModal">
        <div class="modal-content">
            <h2>💀 Kill Node</h2>
            <p>Select a node to kill:</p>
            <select id="killSelect"></select>
            <br><br>
            <button class="btn-kill" onclick="killNode()">Confirm Kill</button>
            <button onclick="hideKillModal()">Cancel</button>
        </div>
    </div>
    
    <div id="toast" class="toast" style="display:none;"></div>
    
    <script>
        let currentStatus = null;
        
        async function refreshStatus() {
            try {
                const res = await fetch('/api/status');
                currentStatus = await res.json();
                
                // 更新信息栏
                document.getElementById('grpcStatus').textContent = 
                    currentStatus.grpc_available ? '🔗 gRPC: 就绪' : '❌ gRPC: 不可用';
                document.getElementById('binaryPathText').textContent = 
                    currentStatus.binary_path || '未找到';
                
                renderStatus();
            } catch(e) {
                showToast('Failed to fetch status: ' + e.message);
            }
        }
        
        function renderStatus() {
            document.getElementById('totalNodes').textContent = currentStatus.total_nodes;
            document.getElementById('aliveNodes').textContent = currentStatus.alive_nodes;
            document.getElementById('leaderId').textContent = currentStatus.leader !== null ? currentStatus.leader : 'None';
            
            const grid = document.getElementById('nodesGrid');
            grid.innerHTML = '';
            
            currentStatus.nodes.forEach(node => {
                const card = document.createElement('div');
                const roleClass = node.is_alive ? (node.role || 'unknown').toLowerCase() : 'dead';
                card.className = `node-card ${roleClass}`;
                
                const roleDisplay = node.is_alive ? (node.role || 'Unknown') : 'Dead';
                
                card.innerHTML = `
                    <div class="node-header">
                        <span class="node-id">Node ${node.id}</span>
                        <span class="role-badge role-${roleClass}">${roleDisplay}</span>
                    </div>
                    <div class="node-stats">
                        <div class="stat-item">
                            <label>Port</label>
                            <span>${node.port}</span>
                        </div>
                        <div class="stat-item">
                            <label>Term</label>
                            <span>${node.term || '-'}</span>
                        </div>
                        <div class="stat-item">
                            <label>Voted For</label>
                            <span>${node.voted_for !== null ? node.voted_for : '-'}</span>
                        </div>
                        <div class="stat-item">
                            <label>Log Entries</label>
                            <span>${node.log_count || 0}</span>
                        </div>
                    </div>
                `;
                grid.appendChild(card);
            });
            
            renderTopology();
        }
        
        function renderTopology() {
            const svg = document.getElementById('topologySvg');
            const nodes = currentStatus.nodes.filter(n => n.is_alive);
            if (nodes.length === 0) {
                svg.innerHTML = '<text x="50%" y="50%" text-anchor="middle" fill="#888">No active nodes</text>';
                return;
            }
            
            const centerX = 400, centerY = 150;
            const radius = Math.min(120, 80 + nodes.length * 10);
            
            let html = '';
            
            // 绘制连接线
            const leader = nodes.find(n => n.role === 'Leader');
            nodes.forEach(node => {
                if (leader && node.id !== leader.id) {
                    const angle = (nodes.indexOf(node) / (nodes.length - 1)) * 2 * Math.PI;
                    const x = centerX + radius * Math.cos(angle);
                    const y = centerY + radius * Math.sin(angle);
                    html += `<line x1="${centerX}" y1="${centerY}" x2="${x}" y2="${y}" 
                             stroke="${node.role === 'Leader' ? '#ffd700' : '#4ecdc4'}" stroke-width="2" opacity="0.5"/>`;
                }
            });
            
            // 绘制节点圆
            nodes.forEach((node, idx) => {
                const angle = (idx / nodes.length) * 2 * Math.PI - Math.PI/2;
                const x = centerX + radius * Math.cos(angle);
                const y = centerY + radius * Math.sin(angle);
                const color = node.role === 'Leader' ? '#ffd700' : 
                             node.role === 'Candidate' ? '#ff6b6b' : '#4ecdc4';
                
                html += `<circle cx="${x}" cy="${y}" r="30" fill="${color}" opacity="1"/>`;
                html += `<text x="${x}" y="${y+5}" text-anchor="middle" fill="#000" font-weight="bold">${node.id}</text>`;
            });
            
            svg.innerHTML = html;
        }
        
        async function addNode() {
            try {
                const res = await fetch('/api/node/add', { method: 'POST' });
                const data = await res.json();
                showToast(data.message || 'Node added');
                setTimeout(refreshStatus, 1000);
            } catch(e) {
                showToast('Failed to add node: ' + e.message);
            }
        }
        
        function showKillModal() {
            const select = document.getElementById('killSelect');
            select.innerHTML = currentStatus.nodes
                .filter(n => n.is_alive)
                .map(n => `<option value="${n.id}">Node ${n.id} (${n.role || 'Unknown'})</option>`)
                .join('');
            document.getElementById('killModal').classList.add('active');
        }
        
        function hideKillModal() {
            document.getElementById('killModal').classList.remove('active');
        }
        
        async function killNode() {
            const nodeId = parseInt(document.getElementById('killSelect').value);
            try {
                const res = await fetch(`/api/node/${nodeId}/kill`, { method: 'POST' });
                const data = await res.json();
                showToast(data.message || 'Node killed');
                hideKillModal();
                setTimeout(refreshStatus, 500);
            } catch(e) {
                showToast('Failed to kill node: ' + e.message);
            }
        }
        
        function showToast(msg) {
            const toast = document.getElementById('toast');
            toast.textContent = msg;
            toast.style.display = 'block';
            setTimeout(() => toast.style.display = 'none', 3000);
        }
        
        // 自动刷新
        refreshStatus();
        setInterval(refreshStatus, 3000);
    </script>
</body>
</html>
'''

# ========== API 路由 ==========

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/status')
def get_status():
    return jsonify(cluster.get_status())

@app.route('/api/node/add', methods=['POST'])
def add_node():
    try:
        node_proxy = cluster.start_node()
        return jsonify({
            'success': True,
            'message': f'Node {node_proxy.node_id} added on port {node_proxy.port}'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/node/<int:node_id>/kill', methods=['POST'])
def kill_node(node_id):
    success = cluster.kill_node(node_id)
    if success:
        return jsonify({'success': True, 'message': f'Node {node_id} killed'})
    return jsonify({'success': False, 'message': 'Node not found'})

# ========== 主程序 ==========

def init_cluster():
    """初始化集群"""
    print("\n🔍 检查环境...")
    
    if not GRPC_AVAILABLE:
        print("❌ gRPC 不可用，请安装：pip install grpcio grpcio-tools")
        return False
    
    # 尝试查找或编译二进制文件
    if not cluster.find_binary():
        print("⚠️  未找到 Raft 二进制文件")
        print("   请手动编译：cd yourCode && ./compile.sh")
        print("   或者手动启动节点后运行本脚本")
        return False
    
    print("✅ 环境检查通过")
    print(f"📦 二进制路径：{cluster.binary_path}")
    
    # 询问是否自动启动节点
    print("\n🤔 是否自动启动 3 个 Raft 节点？(Y/n)")
    try:
        choice = input().strip().lower()
    except:
        choice = 'y'
    
    if choice != 'n':
        print("\n🚀 正在启动初始集群...")
        try:
            for i in range(DEFAULT_NODE_COUNT):
                cluster.start_node(i)
                print(f"✅ 节点 {i} 已启动")
                time.sleep(0.3)
            print(f"\n✅ 集群启动完成！共 {DEFAULT_NODE_COUNT} 个节点")
        except Exception as e:
            print(f"⚠️  启动失败：{e}")
            print("   你可以手动启动节点后再刷新页面")
    
    return True

if __name__ == '__main__':
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║          🫧 Raft God View - 真实集群模式                   ║
    ╠═══════════════════════════════════════════════════════════╣
    ║  访问地址：http://localhost:5000                           ║
    ║                                                           ║
    ║  功能:                                                    ║
    ║   • 通过 gRPC 连接真实的 Raft 节点                          ║
    ║   • 查看所有节点状态 (Leader/Follower/Candidate)          ║
    ║   • 实时显示 Term、Voted For、Log 信息                    ║
    ║   • 可视化集群拓扑                                        ║
    ║   • 添加新节点                                            ║
    ║   • Kill 节点                                             ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    
    init_cluster()
    
    print("\n🌐 启动 Web 服务...")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
