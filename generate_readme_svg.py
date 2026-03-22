#!/usr/bin/env python3
"""
生成 README 的 SVG 可视化图表
用于在 README.md 中展示动态/静态的可视化内容
"""

import os

def generate_profile_svg():
    """生成个人 Profile 可视化 SVG"""
    
    svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="800" height="400" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <!-- 渐变定义 -->
    <linearGradient id="bgGradient" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#1a1a2e;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#16213e;stop-opacity:1" />
    </linearGradient>
    
    <linearGradient id="accentGradient" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:#00d9ff;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#00ff88;stop-opacity:1" />
    </linearGradient>
    
    <!-- 发光效果 -->
    <filter id="glow">
      <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
      <feMerge>
        <feMergeNode in="coloredBlur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>
  
  <!-- 背景 -->
  <rect width="800" height="400" fill="url(#bgGradient)"/>
  
  <!-- 装饰性圆圈 -->
  <circle cx="700" cy="50" r="100" fill="#00d9ff" opacity="0.1"/>
  <circle cx="100" cy="350" r="80" fill="#00ff88" opacity="0.1"/>
  
  <!-- 标题区域 -->
  <text x="400" y="80" text-anchor="middle" 
        font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" 
        font-size="32" font-weight="bold" fill="url(#accentGradient)" filter="url(#glow)">
    🦞 Agent Workspace
  </text>
  
  <!-- 副标题 -->
  <text x="400" y="110" text-anchor="middle" 
        font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" 
        font-size="16" fill="#888">
    Powered by 飞书妙搭 | Running on Miaoda Cloud
  </text>
  
  <!-- 状态指示器 -->
  <g transform="translate(400, 160)">
    <!-- 在线状态 -->
    <circle cx="0" cy="0" r="8" fill="#00ff88">
      <animate attributeName="opacity" values="1;0.5;1" dur="2s" repeatCount="indefinite"/>
    </circle>
    <text x="20" y="5" font-family="sans-serif" font-size="14" fill="#00ff88">● Online</text>
    
    <!-- 会话数 -->
    <circle cx="100" cy="0" r="8" fill="#00d9ff"/>
    <text x="120" y="5" font-family="sans-serif" font-size="14" fill="#00d9ff">● Active Sessions</text>
    
    <!-- 工具就绪 -->
    <circle cx="250" cy="0" r="8" fill="#ffd700"/>
    <text x="270" y="5" font-family="sans-serif" font-size="14" fill="#ffd700">● Tools Ready</text>
  </g>
  
  <!-- 技能条 -->
  <g transform="translate(100, 220)">
    <text x="0" y="0" font-family="sans-serif" font-size="18" fill="#fff" font-weight="bold">Core Capabilities</text>
    
    <!-- Feishu/Lark -->
    <rect x="0" y="20" width="200" height="8" rx="4" fill="#333"/>
    <rect x="0" y="20" width="180" height="8" rx="4" fill="url(#accentGradient)">
      <animate attributeName="width" values="0;180" dur="1s" fill="freeze"/>
    </rect>
    <text x="210" y="27" font-family="sans-serif" font-size="12" fill="#00d9ff">Feishu/Lark 90%</text>
    
    <!-- Python Automation -->
    <rect x="0" y="40" width="200" height="8" rx="4" fill="#333"/>
    <rect x="0" y="40" width="160" height="8" rx="4" fill="url(#accentGradient)">
      <animate attributeName="width" values="0;160" dur="1s" fill="freeze" begin="0.2s"/>
    </rect>
    <text x="210" y="47" font-family="sans-serif" font-size="12" fill="#00d9ff">Python 80%</text>
    
    <!-- Data Visualization -->
    <rect x="0" y="60" width="200" height="8" rx="4" fill="#333"/>
    <rect x="0" y="60" width="150" height="8" rx="4" fill="url(#accentGradient)">
      <animate attributeName="width" values="0;150" dur="1s" fill="freeze" begin="0.4s"/>
    </rect>
    <text x="210" y="67" font-family="sans-serif" font-size="12" fill="#00d9ff">SVG/Viz 75%</text>
    
    <!-- Memory Management -->
    <rect x="0" y="80" width="200" height="8" rx="4" fill="#333"/>
    <rect x="0" y="80" width="170" height="8" rx="4" fill="url(#accentGradient)">
      <animate attributeName="width" values="0;170" dur="1s" fill="freeze" begin="0.6s"/>
    </rect>
    <text x="210" y="87" font-family="sans-serif" font-size="12" fill="#00d9ff">Memory 85%</text>
  </g>
  
  <!-- 底部装饰 -->
  <line x1="50" y1="350" x2="750" y2="350" stroke="#333" stroke-width="2"/>
  <text x="400" y="375" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#666">
    Last Updated: 2026-03-22 | Status: 🟢 Operational
  </text>
</svg>'''
    
    return svg_content


def generate_architecture_svg():
    """生成系统架构可视化 SVG"""
    
    svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="900" height="500" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="headerGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#2c3e50"/>
      <stop offset="100%" style="stop-color:#34495e"/>
    </linearGradient>
    
    <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
      <polygon points="0 0, 10 3.5, 0 7" fill="#00d9ff"/>
    </marker>
  </defs>
  
  <!-- 背景 -->
  <rect width="900" height="500" fill="#1a1a2e"/>
  
  <!-- 标题 -->
  <rect width="900" height="60" fill="url(#headerGrad)"/>
  <text x="450" y="38" text-anchor="middle" font-family="sans-serif" font-size="24" fill="#fff" font-weight="bold">
    🏗️ Agent Architecture
  </text>
  
  <!-- User Layer -->
  <g transform="translate(50, 90)">
    <rect width="800" height="60" rx="10" fill="#3498db" opacity="0.2" stroke="#3498db" stroke-width="2"/>
    <text x="400" y="35" text-anchor="middle" font-family="sans-serif" font-size="18" fill="#3498db" font-weight="bold">
      👤 User (Feishu/Lark)
    </text>
  </g>
  
  <!-- Arrow down -->
  <line x1="450" y1="150" x2="450" y2="180" stroke="#00d9ff" stroke-width="2" marker-end="url(#arrowhead)"/>
  
  <!-- Agent Core -->
  <g transform="translate(200, 180)">
    <rect width="500" height="120" rx="10" fill="#2ecc71" opacity="0.2" stroke="#2ecc71" stroke-width="2"/>
    <text x="250" y="30" text-anchor="middle" font-family="sans-serif" font-size="16" fill="#2ecc71" font-weight="bold">
      🧠 Agent Core (OpenClaw)
    </text>
    
    <!-- Sub-components -->
    <rect x="20" y="45" width="130" height="50" rx="5" fill="#27ae60" opacity="0.5"/>
    <text x="85" y="75" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#fff">Memory</text>
    
    <rect x="185" y="45" width="130" height="50" rx="5" fill="#27ae60" opacity="0.5"/>
    <text x="250" y="75" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#fff">Tools</text>
    
    <rect x="350" y="45" width="130" height="50" rx="5" fill="#27ae60" opacity="0.5"/>
    <text x="415" y="75" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#fff">Skills</text>
  </g>
  
  <!-- Arrows down -->
  <line x1="250" y1="300" x2="200" y2="340" stroke="#00d9ff" stroke-width="2" marker-end="url(#arrowhead)"/>
  <line x1="450" y1="300" x2="450" y2="340" stroke="#00d9ff" stroke-width="2" marker-end="url(#arrowhead)"/>
  <line x1="650" y1="300" x2="700" y2="340" stroke="#00d9ff" stroke-width="2" marker-end="url(#arrowhead)"/>
  
  <!-- Integration Layer -->
  <g transform="translate(50, 340)">
    <rect width="250" height="100" rx="10" fill="#9b59b6" opacity="0.2" stroke="#9b59b6" stroke-width="2"/>
    <text x="125" y="30" text-anchor="middle" font-family="sans-serif" font-size="14" fill="#9b59b6" font-weight="bold">
      🔌 Feishu Plugin
    </text>
    <text x="125" y="55" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#bbb">IM • Calendar • Bitable</text>
    <text x="125" y="75" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#bbb">Docs • Search • Auth</text>
  </g>
  
  <g transform="translate(325, 340)">
    <rect width="250" height="100" rx="10" fill="#e67e22" opacity="0.2" stroke="#e67e22" stroke-width="2"/>
    <text x="125" y="30" text-anchor="middle" font-family="sans-serif" font-size="14" fill="#e67e22" font-weight="bold">
      📊 Raft God View
    </text>
    <text x="125" y="55" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#bbb">Flask + gRPC</text>
    <text x="125" y="75" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#bbb">SVG Visualization</text>
  </g>
  
  <g transform="translate(600, 340)">
    <rect width="250" height="100" rx="10" fill="#e74c3c" opacity="0.2" stroke="#e74c3c" stroke-width="2"/>
    <text x="125" y="30" text-anchor="middle" font-family="sans-serif" font-size="14" fill="#e74c3c" font-weight="bold">
      🛠️ Dev Tools
    </text>
    <text x="125" y="55" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#bbb">Git • Python • Go</text>
    <text x="125" y="75" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#bbb">Documentation</text>
  </g>
  
  <!-- Bottom bar -->
  <rect y="470" width="900" height="30" fill="#0f0f1a"/>
  <text x="450" y="490" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#666">
    Miaoda Cloud Computer | Linux 6.8.0 | Node v22.22.1 | Python 3.12.3
  </text>
</svg>'''
    
    return svg_content


def main():
    """主函数：生成所有 SVG 并保存到 assets 目录"""
    
    # 创建 assets 目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    assets_dir = os.path.join(script_dir, 'assets')
    os.makedirs(assets_dir, exist_ok=True)
    
    # 生成 Profile SVG
    profile_svg = generate_profile_svg()
    profile_path = os.path.join(assets_dir, 'profile.svg')
    with open(profile_path, 'w', encoding='utf-8') as f:
        f.write(profile_svg)
    print(f"✅ 生成: {profile_path}")
    
    # 生成 Architecture SVG
    arch_svg = generate_architecture_svg()
    arch_path = os.path.join(assets_dir, 'architecture.svg')
    with open(arch_path, 'w', encoding='utf-8') as f:
        f.write(arch_svg)
    print(f"✅ 生成：{arch_path}")
    
    print(f"\n📂 Assets 目录：{assets_dir}")
    print("\n💡 使用方法:")
    print("在 README.md 中引用:")
    print('![Profile](assets/profile.svg)')
    print('![Architecture](assets/architecture.svg)')


if __name__ == '__main__':
    main()
