#!/usr/bin/env python3
"""Hermes Webchat - Beautiful web interface for Hermes Agent with full memory

Run: ./webchat.sh
Open: http://localhost:8082
"""

import os
import sys
import json
import threading
import time
import yaml
from flask import Flask, render_template_string, request, jsonify
from datetime import datetime

app = Flask(__name__)

PORT = 8082

sessions = {}
sessions_lock = threading.Lock()

def _load_hermes_config():
    """Load model config from ~/.hermes/config.yaml"""
    config_path = os.path.expanduser('~/.hermes/config.yaml')
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        default_model = config.get('model', {}).get('default', 'minimax-m2.7:cloud')
        fallback_models = config.get('model', {}).get('fallback', [])
        base_url = config.get('model', {}).get('base_url', 'http://localhost:11434')
        return default_model, fallback_models, base_url
    except Exception as e:
        print(f"Warning: Could not load config.yaml: {e}")
        return 'minimax-m2.7:cloud', [], 'http://localhost:11434'

def get_or_create_agent(session_id):
    """Get or create a Hermes agent for this session"""
    with sessions_lock:
        if session_id not in sessions:
            if 'HERMES_HOME' not in os.environ:
                os.environ['HERMES_HOME'] = os.path.expanduser('~/.hermes')
            
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from run_agent import AIAgent
            from hermes_state import SessionDB
            
            # Load from config.yaml, with env override fallback
            env_model = os.getenv('HERMES_MODEL')
            env_base_url = os.getenv('HERMES_BASE_URL')
            
            if env_model:
                model = env_model
                base_url = env_base_url or 'http://localhost:11434'
                fallback_models = []
            else:
                default_model, fallback_models, base_url = _load_hermes_config()
                model = default_model
                base_url = env_base_url or base_url
            
            agent = AIAgent(
                model=model,
                base_url=base_url,
                api_key='',
                enabled_toolsets=['terminal', 'file', 'web'],
                platform='webchat',
                skip_memory=False,
                quiet_mode=True,
                verbose_logging=False,
                session_db=None,
            )
            
            sessions[session_id] = {
                'agent': agent,
                'history': [],
                'created_at': time.time(),
                'last_request_time': time.time(),
                'fallback_models': fallback_models,
            }
            print(f"Created Hermes agent for session: {session_id}")
        else:
            sessions[session_id]['last_request_time'] = time.time()
        
        return sessions[session_id]

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hermes Web Agent by Declan2010</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            /* Dark theme (default) */
            --bg-primary: #0f0f1a;
            --bg-secondary: #1a1a2e;
            --bg-tertiary: #252542;
            --accent: #7c3aed;
            --accent-light: #a78bfa;
            --accent-glow: rgba(124, 58, 237, 0.3);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --user-bg: linear-gradient(135deg, #7c3aed 0%, #5b21b6 100%);
            --bot-bg: #252542;
            --border: #2d2d4a;
            --success: #10b981;
            --error: #ef4444;
            --warning: #f59e0b;
            --header-bg: rgba(26, 26, 46, 0.8);
            --input-bg: rgba(26, 26, 46, 0.9);
            --status-bg: rgba(15, 15, 26, 0.95);
        }
        
        [data-theme="light"] {
            /* Light theme */
            --bg-primary: #f1f5f9;
            --bg-secondary: #ffffff;
            --bg-tertiary: #e2e8f0;
            --accent: #7c3aed;
            --accent-light: #5b21b6;
            --accent-glow: rgba(124, 58, 237, 0.15);
            --text-primary: #1e293b;
            --text-secondary: #475569;
            --text-muted: #94a3b8;
            --user-bg: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
            --bot-bg: #ffffff;
            --border: #cbd5e1;
            --success: #059669;
            --error: #dc2626;
            --warning: #d97706;
            --header-bg: rgba(255, 255, 255, 0.9);
            --input-bg: rgba(255, 255, 255, 0.95);
            --status-bg: rgba(241, 245, 249, 0.95);
            --user-text: #ffffff;
            --user-shadow: 0 4px 12px rgba(124, 58, 237, 0.25);
        }
        
        :root {
            --user-text: #ffffff;
            --user-shadow: 0 4px 15px rgba(124, 58, 237, 0.3);
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            height: 100vh;
            margin: 0;
            overflow: hidden;
            transition: background 0.3s, color 0.3s;
        }
        
        /* Animated background */
        .bg-animation {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 0;
            overflow: hidden;
            transition: opacity 0.3s;
        }
        
        .bg-animation::before {
            content: '';
            position: absolute;
            width: 500px;
            height: 500px;
            background: radial-gradient(circle, var(--accent-glow) 0%, transparent 70%);
            top: -100px;
            right: -100px;
            animation: float 15s ease-in-out infinite;
        }
        
        .bg-animation::after {
            content: '';
            position: absolute;
            width: 400px;
            height: 400px;
            background: radial-gradient(circle, rgba(124, 58, 237, 0.15) 0%, transparent 70%);
            bottom: -50px;
            left: -50px;
            animation: float 20s ease-in-out infinite reverse;
        }
        
        @keyframes float {
            0%, 100% { transform: translate(0, 0) scale(1); }
            33% { transform: translate(30px, -30px) scale(1.05); }
            66% { transform: translate(-20px, 20px) scale(0.95); }
        }
        
        /* Header */
        .header {
            background: var(--header-bg);
            backdrop-filter: blur(20px);
            border-bottom: 1px solid var(--border);
            padding: 0.75rem 1.5rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: relative;
            z-index: 10;
            transition: background 0.3s, border-color 0.3s;
        }
        
        .logo {
            display: flex;
            align-items: center;
            gap: 0.6rem;
        }
        
        .logo-icon {
            width: 36px;
            height: 36px;
            background: linear-gradient(135deg, var(--accent) 0%, var(--accent-light) 100%);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1rem;
            animation: pulse 2s ease-in-out infinite;
        }
        
        @keyframes pulse {
            0%, 100% { box-shadow: 0 0 0 0 var(--accent-glow); }
            50% { box-shadow: 0 0 20px 5px var(--accent-glow); }
        }
        
        .logo-text {
            font-weight: 700;
            font-size: 1.2rem;
            background: linear-gradient(135deg, var(--text-primary) 0%, var(--accent-light) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .header-actions {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }
        
        .history-btn {
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 0.4rem 0.6rem;
            font-size: 1.1rem;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .history-btn:hover {
            background: var(--accent);
            border-color: var(--accent);
        }
        
        .status-badge {
            display: flex;
            align-items: center;
            gap: 0.4rem;
            background: rgba(16, 185, 129, 0.1);
            padding: 0.35rem 0.75rem;
            border-radius: 20px;
            font-size: 0.75rem;
            color: var(--success);
        }
        
        .status-dot {
            width: 6px;
            height: 6px;
            background: var(--success);
            border-radius: 50%;
            animation: blink 1.5s ease-in-out infinite;
        }
        
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.4; }
        }
        
        .settings-btn {
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 0.4rem 0.6rem;
            cursor: pointer;
            font-size: 1rem;
            transition: all 0.2s;
        }
        
        .settings-btn:hover {
            background: var(--accent);
            border-color: var(--accent);
        }
        
        /* Settings Modal */
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 100;
            backdrop-filter: blur(5px);
        }
        
        .modal-overlay.show {
            display: flex;
        }
        
        .modal {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 1.5rem;
            width: 320px;
            max-width: 90%;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        }
        
        .modal h3 {
            font-size: 1.1rem;
            margin-bottom: 1rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .modal-close {
            margin-top: 1rem;
            width: 100%;
            padding: 0.6rem;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text-secondary);
            cursor: pointer;
            font-size: 0.9rem;
        }
        
        .modal-close:hover {
            background: var(--accent);
            color: white;
        }
        
        /* Sidebar */
        .sidebar {
            width: 260px;
            min-width: 260px;
            height: 100vh;
            max-height: 100vh;
            background: var(--bg-secondary);
            border-right: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            overflow: hidden;
            position: relative;
        }
        
        .sidebar.collapsed {
            /* Sidebar is always visible - no collapsing */
        }
        
        .sidebar-header {
            padding: 1rem;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-shrink: 0;
        }
        
        .sidebar-header h3 {
            margin: 0;
            font-size: 0.9rem;
            color: var(--text-primary);
        }
        
        .sidebar-close {
            background: none;
            border: none;
            color: var(--text-muted);
            cursor: pointer;
            font-size: 1.2rem;
            padding: 0.2rem;
        }
        
        .sidebar-close:hover {
            color: var(--text-primary);
        }
        
        .new-chat-btn {
            margin: 0.5rem 1rem;
            padding: 0.6rem;
            background: var(--accent);
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.85rem;
            font-weight: 500;
            transition: background 0.2s;
            flex-shrink: 0;
        }
        
        .new-chat-btn:hover {
            background: var(--accent-light);
        }
        
        .history-list {
            flex: 1;
            overflow-y: auto;
            padding: 0.5rem;
            min-height: 0;
        }
        
        .history-item {
            padding: 0.6rem 0.75rem;
            padding-right: 2rem;
            border: 1px solid transparent;
            border-radius: 8px;
            margin-bottom: 0.3rem;
            cursor: pointer;
            transition: all 0.2s;
            position: relative;
        }
        
        .history-item:hover {
            background: var(--bg-tertiary);
        }
        
        .delete-chat-btn {
            position: absolute;
            top: 4px;
            right: 4px;
            background: none;
            border: none;
            color: var(--text-muted);
            cursor: pointer;
            font-size: 0.8rem;
            padding: 2px 4px;
            border-radius: 4px;
            opacity: 0.3;
            transition: opacity 0.2s;
        }
        
        .history-item:hover .delete-chat-btn {
            opacity: 1 !important;
        }
        
        .delete-chat-btn:hover {
            background: #ef4444 !important;
            color: white !important;
            opacity: 1 !important;
        }
        
        .history-item.active {
            background: var(--accent);
            color: white;
            border-color: var(--accent);
        }
        
        .history-item.active .history-item-title,
        .history-item.active .history-item-date,
        .history-item.active .history-item-preview {
            color: white;
        }
        
        .history-item-title {
            font-weight: 500;
            font-size: 0.85rem;
            color: var(--text-primary);
            margin-bottom: 0.15rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        .history-item-date {
            font-size: 0.7rem;
            color: var(--text-muted);
        }
        
        .history-item-preview {
            font-size: 0.75rem;
            color: var(--text-secondary);
            margin-top: 0.15rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        .history-empty {
            text-align: center;
            color: var(--text-muted);
            padding: 2rem;
            font-size: 0.85rem;
        }
        
        .main-content {
            flex: 1;
            display: flex;
            flex-direction: column;
            min-width: 0;
            height: 100vh;
        }
        
        .setting-item {
            position: absolute;
            top: 1rem;
            right: 1rem;
            background: none;
            border: none;
            color: var(--text-muted);
            font-size: 1.2rem;
            cursor: pointer;
        }
        
        .setting-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.75rem 0;
            border-bottom: 1px solid var(--border);
        }
        
        .setting-item:last-child {
            border-bottom: none;
        }
        
        .setting-label {
            font-size: 0.9rem;
            color: var(--text-secondary);
        }
        
        .toggle {
            position: relative;
            width: 50px;
            height: 26px;
            background: var(--bg-tertiary);
            border-radius: 13px;
            cursor: pointer;
            transition: background 0.3s;
        }
        
        .toggle.active {
            background: var(--accent);
        }
        
        .toggle::after {
            content: '';
            position: absolute;
            top: 3px;
            left: 3px;
            width: 20px;
            height: 20px;
            background: white;
            border-radius: 50%;
            transition: transform 0.3s;
        }
        
        .toggle.active::after {
            transform: translateX(24px);
        }
        
        .theme-options {
            display: flex;
            gap: 0.5rem;
        }
        
        .theme-btn {
            padding: 0.4rem 0.8rem;
            border: 2px solid var(--border);
            border-radius: 8px;
            background: var(--bg-tertiary);
            color: var(--text-secondary);
            cursor: pointer;
            font-size: 0.85rem;
            transition: all 0.2s;
        }
        
        .theme-btn.active {
            border-color: var(--accent);
            background: rgba(124, 58, 237, 0.1);
            color: var(--accent-light);
        }
        
        /* Chat container */
        #chat {
            flex: 1;
            overflow-y: auto;
            padding: 1.5rem;
            display: flex;
            flex-direction: column;
            gap: 1rem;
            position: relative;
            z-index: 5;
        }
        
        #chat::-webkit-scrollbar {
            width: 6px;
        }
        
        #chat::-webkit-scrollbar-track {
            background: transparent;
        }
        
        #chat::-webkit-scrollbar-thumb {
            background: var(--border);
            border-radius: 3px;
        }
        
        /* Timestamps */
        .timestamp {
            font-size: 0.7rem;
            margin-bottom: 0.25rem;
            opacity: 0.7;
            font-weight: 500;
        }
        
        .message.user .timestamp {
            text-align: right;
            margin-left: auto;
            color: rgba(255, 255, 255, 0.8);
        }
        
        .message.assistant .timestamp {
            text-align: left;
            margin-right: auto;
            color: rgba(255, 255, 255, 0.5);
        }
        
        /* Light theme overrides */
        [data-theme="light"] .message.user .timestamp {
            color: rgba(255, 255, 255, 0.95);
        }
        
        [data-theme="light"] .message.assistant .timestamp {
            color: rgba(30, 41, 59, 0.55);
        }
        
        /* Messages */
        .message {
            max-width: 75%;
            padding: 0.85rem 1.1rem;
            border-radius: 18px;
            line-height: 1.65;
            white-space: pre-wrap;
            word-wrap: break-word;
            animation: slideIn 0.3s ease-out;
            position: relative;
            display: flex;
            flex-direction: column;
        }
        
        .message .content {
            flex: 1;
        }
        
        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .message.user {
            align-self: flex-end;
            background: var(--user-bg);
            border-bottom-right-radius: 6px;
            box-shadow: var(--user-shadow);
            color: var(--user-text);
        }
        
        .message.assistant {
            align-self: flex-start;
            background: var(--bot-bg);
            border: 1px solid var(--border);
            border-bottom-left-radius: 6px;
            color: var(--text-primary);
        }
        
        .message.assistant::before {
            content: '🤖';
            position: absolute;
            left: -26px;
            top: 50%;
            transform: translateY(-50%);
            font-size: 1.1rem;
        }
        
        .message.system {
            align-self: center;
            background: transparent;
            color: var(--text-muted);
            font-size: 0.8rem;
            text-align: center;
            padding: 0.4rem;
        }
        
        /* Typing indicator */
        .typing {
            align-self: flex-start;
            background: var(--bot-bg);
            border: 1px solid var(--border);
            padding: 0.85rem 1.25rem;
            border-radius: 18px;
            border-bottom-left-radius: 6px;
            display: none;
        }
        
        .typing.show { display: flex; align-items: center; gap: 0.5rem; }
        
        .typing-dots {
            display: flex;
            gap: 4px;
        }
        
        .typing-dots span {
            width: 7px;
            height: 7px;
            background: var(--accent-light);
            border-radius: 50%;
            animation: bounce 1.4s ease-in-out infinite;
        }
        
        .typing-dots span:nth-child(2) { animation-delay: 0.2s; }
        .typing-dots span:nth-child(3) { animation-delay: 0.4s; }
        
        @keyframes bounce {
            0%, 60%, 100% { transform: translateY(0); }
            30% { transform: translateY(-8px); }
        }
        
        /* Input area */
        .input-area {
            background: var(--input-bg);
            backdrop-filter: blur(20px);
            border-top: 1px solid var(--border);
            padding: 1rem 1.5rem;
            position: relative;
            z-index: 10;
            transition: background 0.3s, border-color 0.3s;
        }
        
        .input-container {
            display: flex;
            gap: 0.75rem;
            max-width: 900px;
            margin: 0 auto;
            align-items: flex-end;
        }
        
        .input-wrapper {
            flex: 1;
            position: relative;
        }
        
        #messageInput {
            width: 100%;
            background: var(--bg-tertiary);
            border: 2px solid var(--border);
            border-radius: 25px;
            padding: 0.85rem 1.25rem;
            color: var(--text-primary);
            font-size: 0.95rem;
            font-family: inherit;
            resize: none;
            min-height: 48px;
            max-height: 150px;
            transition: border-color 0.3s, box-shadow 0.3s, background 0.3s;
        }
        
        #messageInput:focus {
            outline: none;
            border-color: var(--accent);
            box-shadow: 0 0 0 4px var(--accent-glow);
        }
        
        #messageInput::placeholder {
            color: var(--text-muted);
        }
        
        #sendBtn {
            background: linear-gradient(135deg, var(--accent) 0%, #5b21b6 100%);
            color: white;
            border: none;
            border-radius: 50%;
            width: 48px;
            height: 48px;
            font-size: 1.1rem;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        #sendBtn:hover:not(:disabled) {
            transform: scale(1.05);
            box-shadow: 0 4px 20px var(--accent-glow);
        }
        
        #sendBtn:active:not(:disabled) {
            transform: scale(0.95);
        }
        
        #sendBtn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        /* Status bar */
        .status-bar {
            background: var(--status-bg);
            border-top: 1px solid var(--border);
            padding: 0.6rem 1.5rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            color: var(--text-secondary);
            position: relative;
            z-index: 10;
            transition: background 0.3s, border-color 0.3s;
        }
        
        .status-left {
            display: flex;
            align-items: center;
            gap: 1rem;
        }
        
        .status-item {
            display: flex;
            align-items: center;
            gap: 0.4rem;
        }
        
        .status-item .icon {
            color: var(--accent-light);
        }
        
        .context-bar {
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .context-bar .bar {
            width: 100px;
            height: 6px;
            background: var(--bg-tertiary);
            border-radius: 3px;
            overflow: hidden;
        }
        
        .context-bar .bar-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--accent) 0%, var(--accent-light) 100%);
            border-radius: 3px;
            transition: width 0.5s ease-out;
        }
        
        .context-bar.warning .bar-fill {
            background: linear-gradient(90deg, var(--warning) 0%, #fbbf24 100%);
        }
        
        .context-bar.danger .bar-fill {
            background: linear-gradient(90deg, var(--error) 0%, #f87171 100%);
        }
        
        .status-right {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            color: var(--text-muted);
        }
        
        /* Welcome message */
        .welcome {
            text-align: center;
            padding: 2.5rem 1.5rem;
            animation: fadeIn 0.5s ease-out;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        .welcome-icon {
            font-size: 3.5rem;
            margin-bottom: 0.75rem;
            animation: float 3s ease-in-out infinite;
        }
        
        .welcome h2 {
            font-size: 1.3rem;
            margin-bottom: 0.4rem;
            background: linear-gradient(135deg, var(--text-primary) 0%, var(--accent-light) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .welcome p {
            color: var(--text-secondary);
            font-size: 0.9rem;
        }
        
        /* Mobile */
        @media (max-width: 640px) {
            .header { padding: 0.6rem 1rem; }
            .logo-text { font-size: 1rem; }
            #chat { padding: 1rem; }
            .message { max-width: 88%; }
            .input-area { padding: 0.75rem 1rem; }
            .status-bar { 
                padding: 0.5rem 1rem;
                font-size: 0.65rem;
                flex-wrap: wrap;
                gap: 0.5rem;
            }
            .context-bar .bar { width: 60px; }
        }
    </style>
</head>
<body>
    <div class="bg-animation"></div>
    
    <div style="display:flex;height:100vh;overflow:hidden;">
    <div class="sidebar" id="sidebar">
        <div class="sidebar-header" style="flex-wrap:wrap;">
            <h3>💬 Chats</h3>
        </div>
        <div style="padding:0.5rem 1rem;flex-shrink:0;">
            <button class="new-chat-btn" onclick="newChat()" style="width:100%;margin:0;">+ New Chat</button>
        </div>
        <div class="history-list" id="historyList">
            <div class="loading">Loading sessions...</div>
        </div>
    </div>
    <div class="main-content">
    <div class="header">
        <div class="logo">
            <div class="logo-icon">✨</div>
            <div>
                <span class="logo-text">Hermes Web Agent</span>
                <span style="font-size:0.7rem;color:var(--text-secondary);display:block;margin-top:2px;">by Declan2010</span>
            </div>
        </div>
        <div class="header-actions">
            <button class="history-btn" onclick="toggleDisclaimer()" title="Disclaimer">⚠️</button>
            <button class="history-btn" onclick="window.open('https://www.paypal.com/donate/?hosted_button_id=P3TK84JYLNUU6','_blank')" title="Donate">💜</button>
            <div class="status-badge">
                <div class="status-dot"></div>
                <span>Online</span>
            </div>
            <button class="settings-btn" onclick="toggleSettings()">⚙️</button>
        </div>
    </div>
    
    <!-- Settings Modal -->
    <div class="modal-overlay" id="settingsModal">
        <div class="modal">
            <h3>⚙️ Settings</h3>
            <div class="setting-item">
                <span class="setting-label">Theme</span>
                <div class="theme-options">
                    <button class="theme-btn active" data-theme="dark" onclick="setTheme('dark')">🌙</button>
                    <button class="theme-btn" data-theme="light" onclick="setTheme('light')">☀️</button>
                </div>
            </div>
        </div>
    </div>
    
    
    <!-- Disclaimer Modal -->
    <div class="modal-overlay" id="disclaimerModal" onclick="if(event.target===this)toggleDisclaimer()">
        <div class="modal">
            <h3>⚠️ Disclaimer</h3>
            <div style="font-size:0.9rem;line-height:1.7;color:var(--text-secondary);max-height:60vh;overflow-y:auto;padding:0.5rem 0;">
                <p>This software is provided "as is" without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose, and noninfringement.</p>
                <p>In no event shall the developer be liable for any claim, damages, or other liability arising from the use of this software. This includes, but is not limited to, any damage to personal or corporate data, systems, or equipment.</p>
                <p>By installing and/or using Ollama-Agent, you accept full responsibility for any consequences resulting from its operation, including data loss, system modifications, or unauthorized access.</p>
                <p><strong>The AI agent has the ability to execute system commands and modify files — use entirely at your own risk.</strong></p>
            </div>
            <button onclick="toggleDisclaimer()" style="margin-top:1rem;width:100%;background:#8b5cf6;color:white;border:none;padding:0.7rem;border-radius:8px;cursor:pointer;font-size:0.95rem;font-weight:bold;transition:background 0.2s;" onmouseover="this.style.background='#7c3aed'" onmouseout="this.style.background='#8b5cf6'">I Understand</button>
        </div>
    </div>


    
    <div id="chat">
        <div class="welcome">
            <div class="welcome-icon">🤖</div>
            <h2>Hello! I'm Hermes Web Agent</h2>
            <p>Your AI assistant with persistent memory</p>
        </div>
    </div>
    
    <div class="typing" id="typing">
        <div class="typing-dots">
            <span></span>
            <span></span>
            <span></span>
        </div>
        <span>Hermes is thinking...</span>
    </div>
    
    <div class="input-area">
        <div class="input-container">
            <div class="input-wrapper">
                <textarea id="messageInput" placeholder="Type your message..." rows="1"></textarea>
            </div>
            <button id="sendBtn">➤</button>
        </div>
    </div>
    
    <div class="status-bar">
        <div class="status-left">
            <div class="status-item">
                <span class="icon">⚕</span>
                <span id="modelName">minimax-m2.7</span>
            </div>
            <div class="context-bar" id="contextBar">
                <span id="contextPercent">0%</span>
                <div class="bar">
                    <div class="bar-fill" id="contextFill" style="width: 0%"></div>
                </div>
                <span id="contextUsed">0K</span>
            </div>
        </div>
        <div class="status-right">
            <span>⏱</span>
            <span id="sessionTime">0m</span>
        </div>
    </div>
    
    <script>
        const chat = document.getElementById('chat');
        const input = document.getElementById('messageInput');
        const sendBtn = document.getElementById('sendBtn');
        const typing = document.getElementById('typing');
        const welcome = document.querySelector('.welcome');
        const modelName = document.getElementById('modelName');
        const contextUsed = document.getElementById('contextUsed');
        const contextFill = document.getElementById('contextFill');
        const contextPercent = document.getElementById('contextPercent');
        const contextBar = document.getElementById('contextBar');
        const sessionTime = document.getElementById('sessionTime');
        const settingsModal = document.getElementById('settingsModal');

        let sessionStartTime = Date.now();
        
        // Load saved theme
        const savedTheme = localStorage.getItem('hermes-theme') || 'dark';
        document.documentElement.setAttribute('data-theme', savedTheme);
        updateThemeButtons(savedTheme);
        
        function formatTime(ms) {
            const seconds = Math.floor(ms / 1000);
            const minutes = Math.floor(seconds / 60);
            const hours = Math.floor(minutes / 60);
            
            if (hours > 0) {
                return `${hours}h ${minutes % 60}m`;
            } else if (minutes > 0) {
                return `${minutes}m ${seconds % 60}s`;
            } else {
                return `${seconds}s`;
            }
        }
        
        function updateTime() {
            const elapsed = Date.now() - sessionStartTime;
            sessionTime.textContent = formatTime(elapsed);
        }
        
        setInterval(updateTime, 1000);
        
        function updateContext(tokens, maxTokens) {
            const percent = Math.round((tokens / maxTokens) * 100);
            const tokensK = (tokens / 1000).toFixed(1);
            
            contextPercent.textContent = percent + '%';
            contextUsed.textContent = tokensK + 'K';
            contextFill.style.width = percent + '%';
            
            contextBar.classList.remove('warning', 'danger');
            if (percent > 80) {
                contextBar.classList.add('danger');
            } else if (percent > 60) {
                contextBar.classList.add('warning');
            }
        }
        
        function toggleSettings() {
            settingsModal.classList.toggle('show');
        }
        
        function toggleDisclaimer() {
            document.getElementById('disclaimerModal').classList.toggle('show');
        }

        function toggleHistory() {
            // Sidebar is always visible, just refresh sessions
            loadSessions();
        }

        async function newChat() {
            try {
                const res = await fetch('/api/session/new', { method: 'POST' });
                const data = await res.json();
                if (data.session_id) {
                    // Set cookie for new session
                    document.cookie = 'hermes_session=' + data.session_id + ';path=/;max-age=31536000';
                    // Clear chat area
                    chat.innerHTML = '<div class="welcome"><div class="welcome-icon">\U0001f916</div><h2>Hello! Hermes Web Agent</h2><p>Your AI assistant with persistent memory</p></div>';
                    // Reset history
                    currentHistory = [];
                    // Reload sessions list
                    loadSessions();
                }
            } catch (err) {
                console.error('Error creating new chat:', err);
            }
        }
        
        async function loadSessions() {
            const historyList = document.getElementById('historyList');
            historyList.innerHTML = '<div class="loading">Loading sessions...</div>';
            
            try {
                const response = await fetch('/api/sessions');
                const data = await response.json();
                
                if (data.error) {
                    historyList.innerHTML = '<div class="history-empty">Error loading sessions</div>';
                    return;
                }
                
                const sessions = data.sessions || [];
                
                if (sessions.length === 0) {
                    historyList.innerHTML = '<div class="history-empty">No saved sessions yet</div>';
                    return;
                }
                
                // Use data-id attributes and event delegation instead of inline onclick
                historyList.innerHTML = sessions.map((s, idx) => `
                    <div class="history-item" data-session-id="${escapeHtml(s.id || '')}" style="position:relative;">
                        <button class="delete-chat-btn" data-delete-id="${escapeHtml(s.id || '')}" title="Delete chat" class="delete-chat-btn">🗑️</button>
                        <div class="history-item-title">${escapeHtml(s.title || (s.preview ? s.preview.slice(0, 30) : 'Untitled'))}</div>
                        <div class="history-item-date">${s.started_at ? new Date(s.started_at * 1000).toLocaleString() : ''}</div>
                        <div class="history-item-preview">${escapeHtml(s.preview || '')}</div>
                    </div>
                `).join('');
                
                // Add click handlers using event delegation
                historyList.querySelectorAll('.history-item').forEach(item => {
                    item.addEventListener('click', (e) => {
                        // Don't trigger if delete button was clicked
                        if (e.target.classList.contains('delete-chat-btn')) return;
                        const sessionId = item.getAttribute('data-session-id');
                        if (sessionId) {
                            loadSession(sessionId);
                        }
                    });
                });
                
                // Add delete handlers
                historyList.querySelectorAll('.delete-chat-btn').forEach(btn => {
                    btn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        const sessionId = btn.getAttribute('data-delete-id');
                        if (sessionId && confirm('Delete this chat?')) {
                            deleteSession(sessionId);
                        }
                    });
                });
            } catch (err) {
                historyList.innerHTML = '<div class="history-empty">Error: ' + err.message + '</div>';
            }
        }
        
        async function deleteSession(sessionId) {
            try {
                const res = await fetch('/api/sessions/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ session_id: sessionId })
                });
                const data = await res.json();
                if (data.success) {
                    loadSessions();
                } else {
                    alert('Error deleting chat: ' + (data.error || 'Unknown error'));
                }
            } catch (err) {
                alert('Error deleting chat: ' + err.message);
            }
        }
        
        async function loadSession(sessionId) {
            if (!sessionId) {
                console.error('loadSession called with empty sessionId');
                return;
            }
            try {
                // First get the messages for this session
                const response = await fetch('/api/sessions/' + sessionId);
                const data = await response.json();
                
                if (data.error) {
                    alert('Error loading session: ' + (data.error || 'Unknown error'));
                    return;
                }
                
                const messages = data.messages || [];
                
                // Load session into server-side history (MUST complete before closing modal)
                const loadResponse = await fetch('/api/sessions/load', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ session_id: sessionId })
                });
                const loadResult = await loadResponse.json();
                
                if (!loadResult.success) {
                    alert('Error loading session history: ' + (loadResult.error || 'Unknown error'));
                    return;
                }
                
                // Now display the messages (server-side history is confirmed loaded)
                if (messages.length > 0) {
                    // Clear current chat
                    chat.innerHTML = '';
                    
                    // Display all messages from the loaded session
                    messages.forEach(msg => {
                        const role = msg.role === 'user' ? 'user' : 'assistant';
                        // Format timestamp from message or use current time
                        const ts = msg.timestamp ? new Date(msg.timestamp * 1000).toLocaleTimeString() : formatTime(new Date());
                        addMessage(role, msg.content || '', ts);
                    });
                    
                    // Update session title if available
                    const sessionData = data;
                    if (sessionData && sessionData.title) {
                        document.title = 'Hermes - ' + sessionData.title;
                    }
                }
                
                // Close the history modal (AFTER everything succeeded)
                toggleHistory();
                
            } catch (err) {
                alert('Error: ' + err.message);
            }
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        function setTheme(theme) {
            document.documentElement.setAttribute('data-theme', theme);
            localStorage.setItem('hermes-theme', theme);
            updateThemeButtons(theme);
        }
        
        function updateThemeButtons(theme) {
            document.querySelectorAll('.theme-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.theme === theme);
            });
        }
        
        // Close modal on outside click
        settingsModal.addEventListener('click', (e) => {
            if (e.target === settingsModal) {
                settingsModal.classList.remove('show');
            }
        });
        
        // Sidebar toggle handled by toggleHistory function

        function getCookie(name) {
            const value = `; ${document.cookie}`;
            const parts = value.split(`; ${name}=`);
            if (parts.length === 2) return parts.pop().split(';').shift();
            return null;
        }

        function setCookie(name, value, days) {
            const expires = new Date(Date.now() + days * 864e5).toUTCString();
            document.cookie = `${name}=${value}; expires=${expires}; path=/`;
        }

        let sessionId = getCookie('hermes_session');
        if (!sessionId) {
            sessionId = 'sess_' + Math.random().toString(36).substr(2, 9);
            setCookie('hermes_session', sessionId, 30);
        }

        function formatTime(date) {
            let h = date.getHours();
            const m = String(date.getMinutes()).padStart(2, '0');
            const ampm = h >= 12 ? 'PM' : 'AM';
            h = h % 12;
            h = h ? h : 12; // 0 should be 12
            return `${h}:${m} ${ampm}`;
        }
        
        function addMessage(role, content, timestamp) {
            if (welcome) welcome.style.display = 'none';
            
            const div = document.createElement('div');
            div.className = 'message ' + role;
            
            // Add timestamp
            const ts = document.createElement('div');
            ts.className = 'timestamp';
            ts.textContent = timestamp || formatTime(new Date());
            div.appendChild(ts);
            
            // Add content
            const contentDiv = document.createElement('div');
            contentDiv.className = 'content';
            contentDiv.textContent = content;
            div.appendChild(contentDiv);
            
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
        }

        async function sendMessage() {
            const text = input.value.trim();
            if (!text) return;
            input.value = '';
            const now = new Date();
            addMessage('user', text, formatTime(now));
            typing.classList.add('show');
            sendBtn.disabled = true;
            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text })
                });
                const data = await response.json();
                typing.classList.remove('show');
                if (data.error) {
                    addMessage('assistant', '⚠️ Error: ' + data.error, formatTime(new Date()));
                } else {
                    addMessage('assistant', data.response, formatTime(new Date()));
                }
                if (data.model) modelName.textContent = data.model.split(':')[0];
                if (data.tokens && data.maxTokens) {
                    updateContext(data.tokens, data.maxTokens);
                }
            } catch (err) {
                typing.classList.remove('show');
                addMessage('assistant', '⚠️ Connection error: ' + err.message, formatTime(new Date()));
            }
            sendBtn.disabled = false;
            input.focus();
        }

        sendBtn.addEventListener('click', sendMessage);
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
        
        input.addEventListener('input', () => {
            input.style.height = 'auto';
            input.style.height = Math.min(input.scrollHeight, 150) + 'px';
        });
        
        input.focus();
        
        // Load sessions on startup
        loadSessions();
    </script>
    </div><!-- /main-content -->
    </div><!-- /sidebar-wrapper -->
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    message = data.get('message', '')
    session_id = request.cookies.get('hermes_session', 'default')
    
    try:
        session = get_or_create_agent(session_id)
        agent = session['agent']
        history = session['history']
        
        # Inject memory as system context instead of prepending to user message
        # This prevents session titles from being 'Relevant memory info...'
        system_message = None
        if agent._memory_store:
            mem_block = ""
            user_block = ""
            if agent._memory_enabled:
                mem_block = agent._memory_store.format_for_system_prompt("memory") or ""
            if agent._user_profile_enabled:
                user_block = agent._memory_store.format_for_system_prompt("user") or ""
            if mem_block or user_block:
                memory_context = "\n\n".join(filter(None, [mem_block, user_block]))
                system_message = f"[RELEVANT MEMORY INFO FOR YOUR RESPONSE]\n\n{memory_context}\n\n[END OF MEMORY]"
        
        # Use run_conversation with full history (like TUI)
        result = agent.run_conversation(
            user_message=message,
            conversation_history=list(history),
            system_message=system_message
        )
        
        response_text = result.get('final_response', str(result))
        
        # Update history with messages from this turn
        if 'messages' in result:
            for msg in result['messages']:
                if msg not in history:
                    history.append(msg)
        
        # Persist messages to DB for session continuity
        try:
            from hermes_state import SessionDB
            db = SessionDB()
            db.ensure_session(session_id, source='webchat', model=agent.model)
            
            # Save user message
            db.append_message(session_id, role='user', content=data.get('message', ''))
            
            # Save assistant response
            db.append_message(session_id, role='assistant', content=response_text)
        except Exception as db_err:
            print(f"Warning: Failed to persist messages to DB: {db_err}")
        
        # Get context info
        context_limit = getattr(agent, 'context_limit', 204800)
        
        # Estimate tokens from messages (rough approximation)
        total_chars = sum(len(str(m.get('content', ''))) for m in history)
        estimated_tokens = int(total_chars / 4)  # Rough: 1 token ≈ 4 chars
        
        return jsonify({
            'response': response_text,
            'model': agent.model,
            'tokens': estimated_tokens,
            'maxTokens': context_limit
        })
    except Exception as e:
        # Try fallback models in order
        fallback_models = session.get('fallback_models', []) if isinstance(session, dict) else []
        if fallback_models:
            print(f"Primary model failed: {e}. Trying fallbacks...")
            for fallback_model in fallback_models:
                try:
                    print(f"Trying fallback model: {fallback_model}")
                    # Create new agent with fallback model
                    agent = AIAgent(
                        model=fallback_model,
                        base_url=session['agent'].base_url,
                        api_key='',
                        enabled_toolsets=['terminal', 'file', 'web'],
                        platform='webchat',
                        skip_memory=False,
                        quiet_mode=True,
                        verbose_logging=False,
                        session_db=session['agent']._session_db,
                    )
                    
                    result = agent.run_conversation(
                        user_message=message,
                        conversation_history=list(history)
                    )
                    response_text = result.get('final_response', str(result))
                    
                    # Update session with new agent
                    session['agent'] = agent
                    session['history'] = history
                    if 'messages' in result:
                        for msg in result['messages']:
                            if msg not in history:
                                history.append(msg)
                    
                    context_limit = getattr(agent, 'context_limit', 204800)
                    total_chars = sum(len(str(m.get('content', ''))) for m in history)
                    estimated_tokens = int(total_chars / 4)
                    
                    return jsonify({
                        'response': response_text,
                        'model': fallback_model,
                        'tokens': estimated_tokens,
                        'maxTokens': context_limit
                    })
                except Exception as fallback_err:
                    print(f"Fallback {fallback_model} failed: {fallback_err}")
                    continue
        
        # All models failed
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/sessions', methods=['GET'])
def list_sessions():
    """List all saved sessions from session_db"""
    session_id = request.cookies.get('hermes_session', 'default')
    try:
        from hermes_state import SessionDB
        db = SessionDB()
        sessions = db.list_sessions_rich(limit=50)
        return jsonify({'sessions': sessions or []})
    except Exception as e:
        return jsonify({'sessions': [], 'error': str(e)})

@app.route('/api/sessions/<session_id_to_load>', methods=['GET'])
def get_session_history(session_id_to_load):
    """Get messages from a saved session"""
    try:
        from hermes_state import SessionDB
        db = SessionDB()
        messages = db.get_messages_as_conversation(session_id_to_load)
        return jsonify({'messages': messages or []})
    except Exception as e:
        return jsonify({'messages': [], 'error': str(e)})

@app.route('/api/session/new', methods=['POST'])
def new_session():
    """Create a new session"""
    import uuid
    new_id = datetime.now().strftime('%Y%m%d_%H%M%S_') + uuid.uuid4().hex[:6]
    return jsonify({'session_id': new_id})

@app.route('/api/sessions/load', methods=['POST'])
def load_session():
    """Load a saved session into current session"""
    data = request.json
    session_id_to_load = data.get('session_id')
    current_session_id = request.cookies.get('hermes_session', 'default')
    
    try:
        from hermes_state import SessionDB
        db = SessionDB()
        messages = db.get_messages_as_conversation(session_id_to_load)
        
        if messages:
            session = get_or_create_agent(current_session_id)
            session['history'] = messages
        
        return jsonify({'success': True, 'messages_loaded': len(messages) if messages else 0})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/sessions/delete', methods=['POST'])
def delete_session():
    """Delete a session"""
    data = request.json
    session_id_to_delete = data.get('session_id')
    if not session_id_to_delete:
        return jsonify({'success': False, 'error': 'No session_id provided'})
    try:
        from hermes_state import SessionDB
        db = SessionDB()
        result = db.delete_session(session_id_to_delete)
        return jsonify({'success': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    print(f"Hermes Webchat starting on http://localhost:{PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)
