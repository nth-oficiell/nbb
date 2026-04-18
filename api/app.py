#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Panel de Contrôle Discord Bot - Version Ultime
Un seul fichier compatible Railway.app / Vercel
Auto-installation des dépendances incluse
"""

import sys
import subprocess
import os
import importlib
import asyncio
import threading
import time
import json
import base64
from datetime import datetime, timedelta
from collections import deque
import logging
from typing import Optional, Dict, List, Any
import traceback

# ============================================================
# AUTO-INSTALLATION DES DÉPENDANCES
# ============================================================
def install_package(package):
    """Installe un package pip si non présent"""
    try:
        importlib.import_module(package.replace("-", "_"))
    except ImportError:
        print(f"📦 Installation de {package}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package, "-q"])
        print(f"✅ {package} installé")

def check_and_install_dependencies():
    """Vérifie et installe toutes les dépendances nécessaires"""
    dependencies = [
        "discord.py>=2.3.0",
        "flask>=2.3.0",
        "flask-socketio>=5.3.0",
        "python-dotenv>=1.0.0",
        "aiohttp>=3.9.0",
        "requests>=2.31.0",
        "Pillow>=10.0.0",
        "python-socketio>=5.10.0",
        "eventlet>=0.34.0",
        "werkzeug>=2.3.0",
    ]
    
    print("🔧 Vérification des dépendances...")
    for dep in dependencies:
        pkg_name = dep.split(">=")[0].replace("-", "_")
        try:
            importlib.import_module(pkg_name)
        except ImportError:
            print(f"📦 Installation de {dep}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep, "-q"])
            print(f"✅ {dep} installé")
    
    print("✨ Toutes les dépendances sont prêtes !")

check_and_install_dependencies()

# ============================================================
# IMPORTS
# ============================================================
import discord
from discord.ext import commands, tasks
from discord import app_commands
from flask import Flask, request, jsonify, render_template_string
from flask_socketio import SocketIO, emit, join_room, leave_room
import requests
from io import BytesIO
import aiohttp
from PIL import Image
import eventlet

# Patch pour éviter les problèmes d'event loop
eventlet.monkey_patch()

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURATION
# ============================================================
TOKEN = os.environ.get('DISCORD_BOT_TOKEN') or os.environ.get('TOKEN')
PORT = int(os.environ.get('PORT', 5000))

if not TOKEN:
    print("❌ ERREUR: Token Discord non trouvé !")
    print("   Définissez DISCORD_BOT_TOKEN ou TOKEN dans les variables d'environnement")
    sys.exit(1)

# ============================================================
# INITIALISATION DISCORD BOT
# ============================================================
intents = discord.Intents.all()
intents.message_content = True
intents.members = True
intents.presences = True
intents.guilds = True
intents.voice_states = True
intents.reactions = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# Cache des messages pour réduire les appels API
message_cache = {}
cache_timestamps = {}
CACHE_DURATION = 30  # secondes
message_queue = deque(maxlen=1000)  # Pour les messages récents

# Statistiques du bot
bot_stats = {
    'start_time': datetime.now(),
    'messages_sent': 0,
    'commands_used': 0,
    'reactions_added': 0
}

# ============================================================
# INITIALISATION FLASK ET SOCKET.IO
# ============================================================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', logger=False, engineio_logger=False)

# ============================================================
# HTML TEMPLATE (Frontend complet)
# ============================================================
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Panel de Contrôle Discord</title>
    
    <!-- Fonts -->
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    
    <!-- Font Awesome 6 -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css">
    
    <!-- Socket.IO -->
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    
    <style>
        :root {
            --bg-primary: #313338;
            --bg-secondary: #2b2d31;
            --bg-tertiary: #1e1f22;
            --bg-hover: #3c3f45;
            --bg-message-hover: #2e3035;
            --text-normal: #dbdee1;
            --text-muted: #9ba1a9;
            --text-header: #f2f3f5;
            --brand: #5865f2;
            --brand-hover: #4752c4;
            --green: #23a55a;
            --yellow: #f0b232;
            --red: #f23f42;
            --orange: #f47b20;
            --purple: #9b59b6;
            --channel-icon: #80848e;
            --interactive-normal: #b5bac1;
            --border-color: #3f4147;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-primary);
            color: var(--text-normal);
            overflow: hidden;
            height: 100vh;
            margin: 0;
        }
        
        #app {
            display: flex;
            height: 100vh;
            width: 100vw;
        }
        
        /* ===== BARRE DES SERVEURS (72px) ===== */
        .servers-bar {
            width: 72px;
            background: var(--bg-tertiary);
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 12px 0;
            overflow-y: auto;
            flex-shrink: 0;
        }
        
        .server-icon {
            width: 48px;
            height: 48px;
            background: var(--bg-primary);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 8px;
            cursor: pointer;
            position: relative;
            transition: all 0.2s ease;
            color: var(--green);
            font-weight: 600;
            font-size: 16px;
        }
        
        .server-icon img {
            width: 100%;
            height: 100%;
            border-radius: 50%;
            object-fit: cover;
        }
        
        .server-icon:hover {
            border-radius: 16px;
            background: var(--brand);
            color: white;
            transform: scale(1.05);
        }
        
        .server-icon.active {
            border-radius: 16px;
            background: var(--brand);
            color: white;
        }
        
        .server-icon.active::before {
            content: '';
            position: absolute;
            left: -16px;
            width: 4px;
            height: 40px;
            background: var(--text-normal);
            border-radius: 0 4px 4px 0;
        }
        
        .server-separator {
            width: 32px;
            height: 2px;
            background: var(--border-color);
            margin: 8px 0;
        }
        
        .server-icon.dm-icon {
            background: var(--brand);
            color: white;
        }
        
        /* ===== BARRE DES SALONS (280px) ===== */
        .channels-bar {
            width: 280px;
            background: var(--bg-secondary);
            display: flex;
            flex-direction: column;
            flex-shrink: 0;
        }
        
        .server-header {
            padding: 12px 16px;
            font-weight: 600;
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            justify-content: space-between;
            cursor: pointer;
            box-shadow: 0 1px 0 rgba(0,0,0,0.2);
        }
        
        .server-header:hover {
            background: var(--bg-hover);
        }
        
        .channels-list {
            flex: 1;
            overflow-y: auto;
            padding: 8px 8px;
        }
        
        .category {
            margin-bottom: 16px;
        }
        
        .category-header {
            display: flex;
            align-items: center;
            padding: 6px 8px;
            color: var(--text-muted);
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            cursor: pointer;
            user-select: none;
        }
        
        .category-header i {
            margin-right: 4px;
            transition: transform 0.2s ease;
            font-size: 12px;
        }
        
        .category-header.collapsed i {
            transform: rotate(-90deg);
        }
        
        .category-header:hover {
            color: var(--text-normal);
        }
        
        .channel-item {
            display: flex;
            align-items: center;
            padding: 8px 8px 8px 16px;
            margin: 2px 0;
            border-radius: 4px;
            cursor: pointer;
            color: var(--text-muted);
            transition: background 0.1s ease;
        }
        
        .channel-item i {
            margin-right: 6px;
            width: 20px;
            text-align: center;
            color: var(--channel-icon);
        }
        
        .channel-item:hover {
            background: var(--bg-hover);
            color: var(--text-normal);
        }
        
        .channel-item.active {
            background: var(--bg-hover);
            color: var(--text-normal);
        }
        
        .channel-item.voice i {
            color: var(--green);
        }
        
        /* ===== ZONE DE CHAT ===== */
        .chat-area {
            flex: 1;
            background: var(--bg-primary);
            display: flex;
            flex-direction: column;
            min-width: 0;
        }
        
        .chat-header {
            padding: 12px 16px;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            background: var(--bg-primary);
        }
        
        .chat-header i {
            margin-right: 8px;
            color: var(--text-muted);
        }
        
        .chat-header h3 {
            font-size: 16px;
            font-weight: 600;
            color: var(--text-header);
        }
        
        .messages-container {
            flex: 1;
            overflow-y: auto;
            padding: 16px;
            display: flex;
            flex-direction: column-reverse;
        }
        
        .messages-list {
            display: flex;
            flex-direction: column;
        }
        
        .message {
            display: flex;
            padding: 8px 16px 8px 72px;
            position: relative;
            animation: messageAppear 0.3s ease;
        }
        
        @keyframes messageAppear {
            from {
                opacity: 0;
                transform: translateY(10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .message:hover {
            background: var(--bg-message-hover);
        }
        
        .message-avatar {
            position: absolute;
            left: 16px;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            overflow: hidden;
        }
        
        .message-avatar img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        
        .message-content {
            flex: 1;
        }
        
        .message-header {
            display: flex;
            align-items: baseline;
            margin-bottom: 4px;
        }
        
        .message-author {
            font-weight: 600;
            color: var(--text-header);
            margin-right: 8px;
        }
        
        .message-author.bot-tag {
            background: var(--brand);
            color: white;
            font-size: 10px;
            padding: 2px 4px;
            border-radius: 4px;
            margin-left: 4px;
        }
        
        .message-time {
            font-size: 12px;
            color: var(--text-muted);
        }
        
        .message-text {
            color: var(--text-normal);
            line-height: 1.4;
            word-wrap: break-word;
        }
        
        .message-actions {
            position: absolute;
            right: 16px;
            top: -8px;
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            padding: 4px;
            display: none;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        }
        
        .message:hover .message-actions {
            display: flex;
            gap: 4px;
        }
        
        .message-action-btn {
            background: none;
            border: none;
            color: var(--text-muted);
            cursor: pointer;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 14px;
            transition: all 0.2s ease;
        }
        
        .message-action-btn:hover {
            background: var(--bg-hover);
            color: var(--text-normal);
            transform: scale(1.1);
        }
        
        .reactions-container {
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
            margin-top: 4px;
        }
        
        .reaction {
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 2px 8px;
            font-size: 14px;
            display: inline-flex;
            align-items: center;
            gap: 4px;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        
        .reaction:hover {
            background: var(--bg-hover);
            border-color: var(--brand);
        }
        
        .reaction.me {
            background: rgba(88, 101, 242, 0.15);
            border-color: var(--brand);
        }
        
        .typing-indicator {
            padding: 8px 16px;
            display: none;
            align-items: center;
            gap: 8px;
            color: var(--text-muted);
        }
        
        .typing-dots {
            display: flex;
            gap: 4px;
        }
        
        .typing-dot {
            width: 8px;
            height: 8px;
            background: var(--text-muted);
            border-radius: 50%;
            animation: typingBounce 1.4s infinite ease-in-out;
        }
        
        .typing-dot:nth-child(1) { animation-delay: 0s; }
        .typing-dot:nth-child(2) { animation-delay: 0.2s; }
        .typing-dot:nth-child(3) { animation-delay: 0.4s; }
        
        @keyframes typingBounce {
            0%, 60%, 100% { transform: translateY(0); }
            30% { transform: translateY(-10px); }
        }
        
        /* ===== BARRE DES MEMBRES (240px) ===== */
        .members-bar {
            width: 240px;
            background: var(--bg-secondary);
            display: flex;
            flex-direction: column;
            flex-shrink: 0;
        }
        
        .members-header {
            padding: 20px 16px 8px;
            font-weight: 600;
            color: var(--text-muted);
            font-size: 12px;
            text-transform: uppercase;
        }
        
        .members-list {
            flex: 1;
            overflow-y: auto;
            padding: 0 8px;
        }
        
        .member-item {
            display: flex;
            align-items: center;
            padding: 6px 8px;
            border-radius: 4px;
            cursor: pointer;
            margin-bottom: 2px;
        }
        
        .member-item:hover {
            background: var(--bg-hover);
        }
        
        .member-avatar {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            margin-right: 12px;
            position: relative;
        }
        
        .member-avatar img {
            width: 100%;
            height: 100%;
            border-radius: 50%;
            object-fit: cover;
        }
        
        .member-status {
            position: absolute;
            bottom: -2px;
            right: -2px;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            border: 2px solid var(--bg-secondary);
        }
        
        .status-online { background: var(--green); }
        .status-idle { background: var(--yellow); }
        .status-dnd { background: var(--red); }
        .status-offline { background: var(--text-muted); }
        
        .member-name {
            flex: 1;
            font-size: 14px;
            color: var(--text-normal);
        }
        
        .member-bot-badge {
            background: var(--brand);
            color: white;
            font-size: 10px;
            padding: 2px 4px;
            border-radius: 4px;
            margin-left: 4px;
        }
        
        /* ===== ZONE DE SAISIE ===== */
        .input-area {
            padding: 16px;
            background: var(--bg-primary);
            border-top: 1px solid var(--border-color);
        }
        
        .input-container {
            display: flex;
            align-items: center;
            background: var(--bg-tertiary);
            border-radius: 8px;
            padding: 8px 16px;
        }
        
        .input-actions {
            display: flex;
            gap: 8px;
            margin-right: 8px;
        }
        
        .input-action-btn {
            background: none;
            border: none;
            color: var(--text-muted);
            cursor: pointer;
            padding: 8px;
            border-radius: 4px;
            transition: all 0.2s ease;
            font-size: 18px;
        }
        
        .input-action-btn:hover {
            background: var(--bg-hover);
            color: var(--text-normal);
            transform: scale(1.1);
        }
        
        .message-input {
            flex: 1;
            background: transparent;
            border: none;
            color: var(--text-normal);
            font-size: 14px;
            padding: 8px 0;
            outline: none;
            resize: none;
            min-height: 40px;
            max-height: 120px;
            font-family: inherit;
        }
        
        .message-input::placeholder {
            color: var(--text-muted);
        }
        
        .send-btn {
            background: none;
            border: none;
            color: var(--text-muted);
            cursor: pointer;
            padding: 8px;
            border-radius: 4px;
            transition: all 0.2s ease;
            font-size: 18px;
        }
        
        .send-btn:hover {
            background: var(--bg-hover);
            color: var(--brand);
            transform: scale(1.1);
        }
        
        /* ===== BARRE D'ACTIONS RAPIDES ===== */
        .quick-actions {
            display: flex;
            gap: 8px;
            padding: 8px 16px;
            border-top: 1px solid var(--border-color);
            background: var(--bg-primary);
            overflow-x: auto;
        }
        
        .quick-action-btn {
            background: var(--bg-secondary);
            border: none;
            color: var(--text-normal);
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 13px;
            display: flex;
            align-items: center;
            gap: 6px;
            white-space: nowrap;
            transition: all 0.2s ease;
        }
        
        .quick-action-btn:hover {
            background: var(--bg-hover);
            transform: scale(1.02);
            box-shadow: 0 2px 8px rgba(88, 101, 242, 0.2);
        }
        
        .quick-action-btn.danger:hover {
            background: var(--red);
        }
        
        .quick-action-btn i {
            font-size: 14px;
        }
        
        /* ===== GRILLE D'ACTIONS ===== */
        .actions-grid {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            padding: 12px 16px;
            border-top: 1px solid var(--border-color);
            background: var(--bg-primary);
            max-height: 120px;
            overflow-y: auto;
        }
        
        .action-badge {
            background: var(--bg-secondary);
            border: none;
            color: var(--text-muted);
            padding: 6px 12px;
            border-radius: 16px;
            cursor: pointer;
            font-size: 12px;
            display: inline-flex;
            align-items: center;
            gap: 4px;
            transition: all 0.2s ease;
            white-space: nowrap;
        }
        
        .action-badge:hover {
            background: var(--brand);
            color: white;
            transform: scale(1.05);
        }
        
        .action-badge i {
            font-size: 12px;
        }
        
        /* ===== MODALS ===== */
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.7);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            animation: fadeIn 0.2s ease;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        .modal {
            background: var(--bg-primary);
            border-radius: 8px;
            width: 500px;
            max-width: 90vw;
            max-height: 90vh;
            overflow: auto;
            box-shadow: 0 4px 24px rgba(0, 0, 0, 0.5);
            animation: slideIn 0.3s ease;
        }
        
        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(-20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .modal-header {
            padding: 16px 20px;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        
        .modal-header h3 {
            font-size: 18px;
            font-weight: 600;
            color: var(--text-header);
        }
        
        .modal-close {
            background: none;
            border: none;
            color: var(--text-muted);
            cursor: pointer;
            font-size: 20px;
            padding: 4px 8px;
            border-radius: 4px;
            transition: all 0.2s ease;
        }
        
        .modal-close:hover {
            background: var(--bg-hover);
            color: var(--text-normal);
        }
        
        .modal-body {
            padding: 20px;
        }
        
        .modal-footer {
            padding: 16px 20px;
            border-top: 1px solid var(--border-color);
            display: flex;
            justify-content: flex-end;
            gap: 8px;
        }
        
        .modal-btn {
            background: var(--bg-secondary);
            border: none;
            color: var(--text-normal);
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.2s ease;
        }
        
        .modal-btn:hover {
            background: var(--bg-hover);
        }
        
        .modal-btn.primary {
            background: var(--brand);
            color: white;
        }
        
        .modal-btn.primary:hover {
            background: var(--brand-hover);
        }
        
        .modal-btn.danger {
            background: var(--red);
            color: white;
        }
        
        .form-group {
            margin-bottom: 16px;
        }
        
        .form-label {
            display: block;
            margin-bottom: 8px;
            color: var(--text-muted);
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
        }
        
        .form-input, .form-select, .form-textarea {
            width: 100%;
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            padding: 10px 12px;
            color: var(--text-normal);
            font-size: 14px;
            font-family: inherit;
            outline: none;
            transition: border-color 0.2s ease;
        }
        
        .form-input:focus, .form-select:focus, .form-textarea:focus {
            border-color: var(--brand);
        }
        
        .form-textarea {
            resize: vertical;
            min-height: 80px;
        }
        
        /* ===== TOAST NOTIFICATIONS ===== */
        .toast-container {
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 10000;
        }
        
        .toast {
            background: var(--bg-tertiary);
            color: var(--text-normal);
            padding: 12px 16px;
            border-radius: 4px;
            margin-top: 8px;
            box-shadow: 0 2px 12px rgba(0, 0, 0, 0.4);
            display: flex;
            align-items: center;
            gap: 12px;
            animation: slideInRight 0.3s ease;
            min-width: 250px;
        }
        
        @keyframes slideInRight {
            from {
                opacity: 0;
                transform: translateX(20px);
            }
            to {
                opacity: 1;
                transform: translateX(0);
            }
        }
        
        .toast.success { border-left: 4px solid var(--green); }
        .toast.error { border-left: 4px solid var(--red); }
        .toast.info { border-left: 4px solid var(--brand); }
        
        .toast i {
            font-size: 20px;
        }
        
        .toast.success i { color: var(--green); }
        .toast.error i { color: var(--red); }
        .toast.info i { color: var(--brand); }
        
        .toast-message {
            flex: 1;
            font-size: 14px;
        }
        
        /* ===== BOT CONTROLS ===== */
        .bot-controls {
            position: fixed;
            bottom: 20px;
            left: 20px;
            background: var(--bg-tertiary);
            border-radius: 8px;
            padding: 12px;
            box-shadow: 0 2px 12px rgba(0, 0, 0, 0.4);
            display: flex;
            gap: 8px;
            z-index: 100;
        }
        
        .status-led {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        
        .status-led.online { background: var(--green); }
        .status-led.idle { background: var(--yellow); }
        .status-led.dnd { background: var(--red); }
        .status-led.offline { background: var(--text-muted); }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .bot-control-btn {
            background: var(--bg-secondary);
            border: none;
            color: var(--text-normal);
            padding: 8px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s ease;
        }
        
        .bot-control-btn:hover {
            background: var(--bg-hover);
        }
        
        /* ===== RESPONSIVE ===== */
        @media (max-width: 1200px) {
            .members-bar {
                display: none;
            }
        }
        
        @media (max-width: 768px) {
            .servers-bar {
                width: 60px;
            }
            
            .channels-bar {
                display: none;
            }
            
            .server-icon {
                width: 40px;
                height: 40px;
            }
            
            .quick-actions {
                flex-wrap: wrap;
            }
            
            .bot-controls {
                bottom: 10px;
                left: 70px;
            }
        }
        
        /* ===== UTILITIES ===== */
        .loading {
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            color: var(--text-muted);
        }
        
        .loading i {
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
        
        ::-webkit-scrollbar {
            width: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: var(--bg-tertiary);
        }
        
        ::-webkit-scrollbar-thumb {
            background: var(--bg-primary);
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: var(--bg-hover);
        }
    </style>
</head>
<body>
    <div id="app">
        <!-- Barre des serveurs -->
        <div class="servers-bar" id="servers-bar">
            <div class="server-icon dm-icon" data-type="dm" title="Messages privés">
                <i class="fa-brands fa-discord"></i>
            </div>
            <div class="server-separator"></div>
            <div id="server-list"></div>
        </div>
        
        <!-- Barre des salons -->
        <div class="channels-bar" id="channels-bar">
            <div class="server-header" id="server-header">
                <span id="current-server-name">Chargement...</span>
                <i class="fas fa-chevron-down"></i>
            </div>
            <div class="channels-list" id="channels-list">
                <div class="loading">
                    <i class="fas fa-spinner"></i>
                </div>
            </div>
        </div>
        
        <!-- Zone de chat -->
        <div class="chat-area" id="chat-area">
            <div class="chat-header">
                <i class="fas fa-hashtag" id="channel-icon"></i>
                <h3 id="current-channel-name">Sélectionnez un salon</h3>
            </div>
            
            <div class="messages-container" id="messages-container">
                <div class="typing-indicator" id="typing-indicator">
                    <span id="typing-text">Quelqu'un écrit...</span>
                    <div class="typing-dots">
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                    </div>
                </div>
                <div class="messages-list" id="messages-list">
                    <div class="loading">
                        <i class="fas fa-spinner"></i> Chargement des messages...
                    </div>
                </div>
            </div>
            
            <!-- Barre d'actions rapides -->
            <div class="quick-actions" id="quick-actions">
                <button class="quick-action-btn" onclick="showModal('kick-modal')">
                    <i class="fas fa-user-slash"></i> Kick
                </button>
                <button class="quick-action-btn danger" onclick="showModal('ban-modal')">
                    <i class="fas fa-ban"></i> Ban
                </button>
                <button class="quick-action-btn" onclick="showModal('role-modal')">
                    <i class="fas fa-tag"></i> Rôle
                </button>
                <button class="quick-action-btn" onclick="clearMessages()">
                    <i class="fas fa-eraser"></i> Clear
                </button>
                <button class="quick-action-btn" onclick="refreshMessages()">
                    <i class="fas fa-sync-alt"></i> Refresh
                </button>
            </div>
            
            <!-- Grille d'actions supplémentaires -->
            <div class="actions-grid" id="actions-grid">
                <button class="action-badge" onclick="showModal('timeout-modal')"><i class="fas fa-clock"></i> Timeout</button>
                <button class="action-badge" onclick="showModal('nickname-modal')"><i class="fas fa-pencil"></i> Nickname</button>
                <button class="action-badge" onclick="showModal('embed-modal')"><i class="fas fa-file-alt"></i> Embed</button>
                <button class="action-badge" onclick="pinMessage()"><i class="fas fa-thumbtack"></i> Épingler</button>
                <button class="action-badge" onclick="showModal('move-modal')"><i class="fas fa-arrows-alt"></i> Déplacer</button>
                <button class="action-badge" onclick="showModal('mute-modal')"><i class="fas fa-microphone-slash"></i> Mute</button>
                <button class="action-badge" onclick="showModal('deafen-modal')"><i class="fas fa-volume-mute"></i> Deafen</button>
                <button class="action-badge" onclick="joinVoice()"><i class="fas fa-phone"></i> Join VC</button>
                <button class="action-badge" onclick="leaveVoice()"><i class="fas fa-phone-slash"></i> Leave VC</button>
                <button class="action-badge" onclick="showModal('status-modal')"><i class="fas fa-circle"></i> Statut</button>
                <button class="action-badge" onclick="showModal('activity-modal')"><i class="fas fa-gamepad"></i> Activité</button>
                <button class="action-badge" onclick="showModal('avatar-modal')"><i class="fas fa-image"></i> Avatar</button>
                <button class="action-badge" onclick="showModal('create-channel-modal')"><i class="fas fa-plus"></i> Salon</button>
                <button class="action-badge" onclick="showModal('delete-channel-modal')"><i class="fas fa-trash"></i> Supprimer</button>
                <button class="action-badge" onclick="showModal('file-modal')"><i class="fas fa-file"></i> Fichier</button>
                <button class="action-badge" onclick="mentionEveryone()"><i class="fas fa-at"></i> @everyone</button>
                <button class="action-badge" onclick="showModal('server-info-modal')"><i class="fas fa-info-circle"></i> Info Serveur</button>
                <button class="action-badge" onclick="exportLogs()"><i class="fas fa-download"></i> Exporter</button>
            </div>
            
            <!-- Zone de saisie -->
            <div class="input-area">
                <div class="input-container">
                    <div class="input-actions">
                        <button class="input-action-btn" onclick="showModal('file-modal')">
                            <i class="fas fa-plus-circle"></i>
                        </button>
                        <button class="input-action-btn" onclick="showEmojiPicker()">
                            <i class="far fa-smile"></i>
                        </button>
                    </div>
                    <textarea class="message-input" id="message-input" placeholder="Envoyer un message..." rows="1"></textarea>
                    <button class="send-btn" onclick="sendMessage()">
                        <i class="fas fa-paper-plane"></i>
                    </button>
                </div>
            </div>
        </div>
        
        <!-- Barre des membres -->
        <div class="members-bar" id="members-bar">
            <div class="members-header">
                <span id="members-count">MEMBRES — 0</span>
            </div>
            <div class="members-list" id="members-list">
                <div class="loading">
                    <i class="fas fa-spinner"></i>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Contrôles du bot -->
    <div class="bot-controls" id="bot-controls">
        <div class="status-led" id="bot-status-led"></div>
        <select class="bot-control-btn" id="status-select" onchange="changeStatus()">
            <option value="online">🟢 En ligne</option>
            <option value="idle">🟡 Absent</option>
            <option value="dnd">🔴 Ne pas déranger</option>
            <option value="offline">⚫ Invisible</option>
        </select>
        <button class="bot-control-btn" onclick="showModal('activity-modal')">
            <i class="fas fa-gamepad"></i>
        </button>
        <button class="bot-control-btn" onclick="showModal('avatar-modal')">
            <i class="fas fa-camera"></i>
        </button>
        <div id="bot-stats" style="font-size: 11px; color: var(--text-muted); margin-left: 8px;">
            Servers: <span id="stats-servers">0</span> | 
            Msg: <span id="stats-messages">0</span>
        </div>
    </div>
    
    <!-- Modals -->
    <div class="modal-overlay" id="modal-overlay" onclick="closeModal(event)">
        <!-- Kick Modal -->
        <div class="modal" id="kick-modal">
            <div class="modal-header">
                <h3>Expulser un membre</h3>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label class="form-label">Membre</label>
                    <select class="form-select" id="kick-member"></select>
                </div>
                <div class="form-group">
                    <label class="form-label">Raison</label>
                    <input type="text" class="form-input" id="kick-reason" placeholder="Raison (optionnel)">
                </div>
            </div>
            <div class="modal-footer">
                <button class="modal-btn" onclick="closeModal()">Annuler</button>
                <button class="modal-btn danger" onclick="executeKick()">Expulser</button>
            </div>
        </div>
        
        <!-- Ban Modal -->
        <div class="modal" id="ban-modal">
            <div class="modal-header">
                <h3>Bannir un membre</h3>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label class="form-label">Membre</label>
                    <select class="form-select" id="ban-member"></select>
                </div>
                <div class="form-group">
                    <label class="form-label">Raison</label>
                    <input type="text" class="form-input" id="ban-reason" placeholder="Raison (optionnel)">
                </div>
                <div class="form-group">
                    <label class="form-label">
                        <input type="checkbox" id="ban-delete-days"> Supprimer les messages (7 jours)
                    </label>
                </div>
            </div>
            <div class="modal-footer">
                <button class="modal-btn" onclick="closeModal()">Annuler</button>
                <button class="modal-btn danger" onclick="executeBan()">Bannir</button>
            </div>
        </div>
        
        <!-- Role Modal -->
        <div class="modal" id="role-modal">
            <div class="modal-header">
                <h3>Gérer les rôles</h3>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label class="form-label">Membre</label>
                    <select class="form-select" id="role-member"></select>
                </div>
                <div class="form-group">
                    <label class="form-label">Rôle</label>
                    <select class="form-select" id="role-select"></select>
                </div>
                <div class="form-group">
                    <label class="form-label">Action</label>
                    <select class="form-select" id="role-action">
                        <option value="add">Ajouter</option>
                        <option value="remove">Retirer</option>
                    </select>
                </div>
            </div>
            <div class="modal-footer">
                <button class="modal-btn" onclick="closeModal()">Annuler</button>
                <button class="modal-btn primary" onclick="executeRole()">Appliquer</button>
            </div>
        </div>
        
        <!-- Timeout Modal -->
        <div class="modal" id="timeout-modal">
            <div class="modal-header">
                <h3>Timeout</h3>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label class="form-label">Membre</label>
                    <select class="form-select" id="timeout-member"></select>
                </div>
                <div class="form-group">
                    <label class="form-label">Durée (minutes)</label>
                    <input type="number" class="form-input" id="timeout-duration" value="5" min="1" max="40320">
                </div>
                <div class="form-group">
                    <label class="form-label">Raison</label>
                    <input type="text" class="form-input" id="timeout-reason" placeholder="Raison (optionnel)">
                </div>
            </div>
            <div class="modal-footer">
                <button class="modal-btn" onclick="closeModal()">Annuler</button>
                <button class="modal-btn primary" onclick="executeTimeout()">Appliquer</button>
            </div>
        </div>
        
        <!-- Nickname Modal -->
        <div class="modal" id="nickname-modal">
            <div class="modal-header">
                <h3>Changer le surnom</h3>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label class="form-label">Membre</label>
                    <select class="form-select" id="nickname-member"></select>
                </div>
                <div class="form-group">
                    <label class="form-label">Nouveau surnom</label>
                    <input type="text" class="form-input" id="nickname-value" placeholder="Laisser vide pour réinitialiser">
                </div>
            </div>
            <div class="modal-footer">
                <button class="modal-btn" onclick="closeModal()">Annuler</button>
                <button class="modal-btn primary" onclick="executeNickname()">Changer</button>
            </div>
        </div>
        
        <!-- Embed Modal -->
        <div class="modal" id="embed-modal">
            <div class="modal-header">
                <h3>Envoyer un Embed</h3>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label class="form-label">Titre</label>
                    <input type="text" class="form-input" id="embed-title" placeholder="Titre de l'embed">
                </div>
                <div class="form-group">
                    <label class="form-label">Description</label>
                    <textarea class="form-textarea" id="embed-description" placeholder="Description"></textarea>
                </div>
                <div class="form-group">
                    <label class="form-label">Couleur (hex)</label>
                    <input type="color" class="form-input" id="embed-color" value="#5865f2">
                </div>
            </div>
            <div class="modal-footer">
                <button class="modal-btn" onclick="closeModal()">Annuler</button>
                <button class="modal-btn primary" onclick="sendEmbed()">Envoyer</button>
            </div>
        </div>
        
        <!-- Status Modal -->
        <div class="modal" id="status-modal">
            <div class="modal-header">
                <h3>Changer le statut</h3>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label class="form-label">Statut</label>
                    <select class="form-select" id="modal-status-select">
                        <option value="online">🟢 En ligne</option>
                        <option value="idle">🟡 Absent</option>
                        <option value="dnd">🔴 Ne pas déranger</option>
                        <option value="offline">⚫ Invisible</option>
                    </select>
                </div>
            </div>
            <div class="modal-footer">
                <button class="modal-btn" onclick="closeModal()">Annuler</button>
                <button class="modal-btn primary" onclick="changeStatusFromModal()">Appliquer</button>
            </div>
        </div>
        
        <!-- Activity Modal -->
        <div class="modal" id="activity-modal">
            <div class="modal-header">
                <h3>Changer l'activité</h3>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label class="form-label">Type d'activité</label>
                    <select class="form-select" id="activity-type">
                        <option value="playing">🎮 Joue à</option>
                        <option value="streaming">📺 Streame</option>
                        <option value="listening">🎵 Écoute</option>
                        <option value="watching">📺 Regarde</option>
                        <option value="competing">🏆 Compétition</option>
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label">Texte</label>
                    <input type="text" class="form-input" id="activity-name" placeholder="Nom de l'activité">
                </div>
            </div>
            <div class="modal-footer">
                <button class="modal-btn" onclick="closeModal()">Annuler</button>
                <button class="modal-btn primary" onclick="changeActivity()">Appliquer</button>
            </div>
        </div>
        
        <!-- Avatar Modal -->
        <div class="modal" id="avatar-modal">
            <div class="modal-header">
                <h3>Changer l'avatar du bot</h3>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label class="form-label">URL de l'image</label>
                    <input type="url" class="form-input" id="avatar-url" placeholder="https://example.com/image.png">
                </div>
                <div class="form-group">
                    <label class="form-label">Ou fichier</label>
                    <input type="file" class="form-input" id="avatar-file" accept="image/*">
                </div>
            </div>
            <div class="modal-footer">
                <button class="modal-btn" onclick="closeModal()">Annuler</button>
                <button class="modal-btn primary" onclick="changeAvatar()">Changer</button>
            </div>
        </div>
        
        <!-- Create Channel Modal -->
        <div class="modal" id="create-channel-modal">
            <div class="modal-header">
                <h3>Créer un salon</h3>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label class="form-label">Nom</label>
                    <input type="text" class="form-input" id="channel-name" placeholder="nom-du-salon">
                </div>
                <div class="form-group">
                    <label class="form-label">Type</label>
                    <select class="form-select" id="channel-type">
                        <option value="text">📝 Texte</option>
                        <option value="voice">🔊 Vocal</option>
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label">Catégorie (optionnel)</label>
                    <select class="form-select" id="channel-category"></select>
                </div>
            </div>
            <div class="modal-footer">
                <button class="modal-btn" onclick="closeModal()">Annuler</button>
                <button class="modal-btn primary" onclick="createChannel()">Créer</button>
            </div>
        </div>
        
        <!-- Delete Channel Modal -->
        <div class="modal" id="delete-channel-modal">
            <div class="modal-header">
                <h3>Supprimer un salon</h3>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label class="form-label">Salon</label>
                    <select class="form-select" id="delete-channel-select"></select>
                </div>
                <p style="color: var(--red); font-size: 12px;">
                    <i class="fas fa-exclamation-triangle"></i> Cette action est irréversible !
                </p>
            </div>
            <div class="modal-footer">
                <button class="modal-btn" onclick="closeModal()">Annuler</button>
                <button class="modal-btn danger" onclick="deleteChannel()">Supprimer</button>
            </div>
        </div>
        
        <!-- File Modal -->
        <div class="modal" id="file-modal">
            <div class="modal-header">
                <h3>Envoyer un fichier</h3>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label class="form-label">Fichier</label>
                    <input type="file" class="form-input" id="file-input">
                </div>
                <div class="form-group">
                    <label class="form-label">Message (optionnel)</label>
                    <input type="text" class="form-input" id="file-message" placeholder="Texte accompagnant le fichier">
                </div>
            </div>
            <div class="modal-footer">
                <button class="modal-btn" onclick="closeModal()">Annuler</button>
                <button class="modal-btn primary" onclick="sendFile()">Envoyer</button>
            </div>
        </div>
        
        <!-- Server Info Modal -->
        <div class="modal" id="server-info-modal">
            <div class="modal-header">
                <h3>Informations du serveur</h3>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body" id="server-info-content">
                <div class="loading"><i class="fas fa-spinner"></i> Chargement...</div>
            </div>
            <div class="modal-footer">
                <button class="modal-btn" onclick="closeModal()">Fermer</button>
            </div>
        </div>
        
        <!-- Move Modal -->
        <div class="modal" id="move-modal">
            <div class="modal-header">
                <h3>Déplacer un membre</h3>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label class="form-label">Membre</label>
                    <select class="form-select" id="move-member"></select>
                </div>
                <div class="form-group">
                    <label class="form-label">Salon vocal</label>
                    <select class="form-select" id="move-channel"></select>
                </div>
            </div>
            <div class="modal-footer">
                <button class="modal-btn" onclick="closeModal()">Annuler</button>
                <button class="modal-btn primary" onclick="executeMove()">Déplacer</button>
            </div>
        </div>
        
        <!-- Mute Modal -->
        <div class="modal" id="mute-modal">
            <div class="modal-header">
                <h3>Mute vocal</h3>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label class="form-label">Membre</label>
                    <select class="form-select" id="mute-member"></select>
                </div>
                <div class="form-group">
                    <label class="form-label">Action</label>
                    <select class="form-select" id="mute-action">
                        <option value="mute">Mute</option>
                        <option value="unmute">Unmute</option>
                    </select>
                </div>
            </div>
            <div class="modal-footer">
                <button class="modal-btn" onclick="closeModal()">Annuler</button>
                <button class="modal-btn primary" onclick="executeMute()">Appliquer</button>
            </div>
        </div>
        
        <!-- Deafen Modal -->
        <div class="modal" id="deafen-modal">
            <div class="modal-header">
                <h3>Deafen</h3>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label class="form-label">Membre</label>
                    <select class="form-select" id="deafen-member"></select>
                </div>
                <div class="form-group">
                    <label class="form-label">Action</label>
                    <select class="form-select" id="deafen-action">
                        <option value="deafen">Deafen</option>
                        <option value="undeafen">Undeafen</option>
                    </select>
                </div>
            </div>
            <div class="modal-footer">
                <button class="modal-btn" onclick="closeModal()">Annuler</button>
                <button class="modal-btn primary" onclick="executeDeafen()">Appliquer</button>
            </div>
        </div>
    </div>
    
    <!-- Toast Container -->
    <div class="toast-container" id="toast-container"></div>
    
    <!-- Socket.IO et Logique JavaScript -->
    <script>
        const socket = io();
        
        // État global
        let currentUser = null;
        let currentServer = null;
        let currentChannel = null;
        let servers = [];
        let channels = [];
        let members = [];
        let messages = [];
        let dms = [];
        let selectedMessage = null;
        
        // Initialisation
        document.addEventListener('DOMContentLoaded', () => {
            loadServers();
            loadDMs();
            loadStats();
            setupMessageInput();
            
            // Socket events
            socket.on('connect', () => {
                console.log('Connected to server');
                showToast('Connecté au serveur', 'success');
            });
            
            socket.on('new_message', (data) => {
                if (data.channel_id === currentChannel) {
                    addMessage(data);
                    updateStats();
                }
            });
            
            socket.on('bot_typing', (data) => {
                const indicator = document.getElementById('typing-indicator');
                const text = document.getElementById('typing-text');
                
                if (data.channel_id === currentChannel) {
                    if (data.typing) {
                        text.textContent = `${data.user} écrit...`;
                        indicator.style.display = 'flex';
                    } else {
                        indicator.style.display = 'none';
                    }
                }
            });
            
            socket.on('member_update', (data) => {
                if (data.server_id === currentServer) {
                    loadMembers(currentServer);
                }
                updateStats();
            });
            
            socket.on('bot_avatar', (data) => {
                showToast('Avatar du bot mis à jour', 'success');
            });
            
            socket.on('message_deleted', (data) => {
                if (data.channel_id === currentChannel) {
                    removeMessage(data.message_id);
                }
            });
            
            socket.on('message_edited', (data) => {
                if (data.channel_id === currentChannel) {
                    updateMessage(data.message_id, data.new_content);
                }
            });
            
            socket.on('reaction_added', (data) => {
                if (data.channel_id === currentChannel) {
                    addReaction(data.message_id, data.emoji, data.user_id);
                }
            });
        });
        
        // Fonctions de chargement
        async function loadServers() {
            try {
                const response = await fetch('/api/servers');
                servers = await response.json();
                displayServers();
                updateStats();
            } catch (error) {
                showToast('Erreur lors du chargement des serveurs', 'error');
            }
        }
        
        async function loadDMs() {
            try {
                const response = await fetch('/api/dms');
                dms = await response.json();
                displayDMs();
            } catch (error) {
                console.error('Error loading DMs:', error);
            }
        }
        
        async function loadChannels(serverId) {
            try {
                const response = await fetch(`/api/channels/${serverId}`);
                channels = await response.json();
                displayChannels();
            } catch (error) {
                showToast('Erreur lors du chargement des salons', 'error');
            }
        }
        
        async function loadMessages(channelId) {
            try {
                const container = document.getElementById('messages-list');
                container.innerHTML = '<div class="loading"><i class="fas fa-spinner"></i> Chargement des messages...</div>';
                
                const response = await fetch(`/api/messages/${channelId}`);
                messages = await response.json();
                displayMessages();
            } catch (error) {
                showToast('Erreur lors du chargement des messages', 'error');
            }
        }
        
        async function loadMembers(serverId) {
            try {
                const response = await fetch(`/api/members/${serverId}`);
                members = await response.json();
                displayMembers();
                updateMembersCount();
            } catch (error) {
                console.error('Error loading members:', error);
            }
        }
        
        async function loadStats() {
            try {
                const response = await fetch('/api/stats');
                const stats = await response.json();
                document.getElementById('stats-servers').textContent = stats.servers;
                document.getElementById('stats-messages').textContent = stats.messages_sent;
            } catch (error) {
                console.error('Error loading stats:', error);
            }
        }
        
        function updateStats() {
            loadStats();
        }
        
        // Fonctions d'affichage
        function displayServers() {
            const container = document.getElementById('server-list');
            container.innerHTML = servers.map(server => `
                <div class="server-icon" data-server-id="${server.id}" onclick="selectServer('${server.id}')" title="${server.name}">
                    ${server.icon ? `<img src="${server.icon}" alt="${server.name}">` : server.name.charAt(0).toUpperCase()}
                </div>
            `).join('');
        }
        
        function displayDMs() {
            // Les DMs sont déjà affichés via l'icône DM
        }
        
        function displayChannels() {
            const container = document.getElementById('channels-list');
            
            // Grouper par catégories
            const categories = {};
            const noCategory = [];
            
            channels.forEach(channel => {
                if (channel.type === 'category') {
                    categories[channel.id] = { ...channel, children: [] };
                }
            });
            
            channels.forEach(channel => {
                if (channel.parent_id) {
                    if (categories[channel.parent_id]) {
                        categories[channel.parent_id].children.push(channel);
                    }
                } else if (channel.type !== 'category') {
                    noCategory.push(channel);
                }
            });
            
            let html = '';
            
            // Salons sans catégorie
            noCategory.forEach(channel => {
                html += createChannelElement(channel);
            });
            
            // Catégories et leurs salons
            Object.values(categories).forEach(category => {
                html += `
                    <div class="category">
                        <div class="category-header" onclick="toggleCategory(this)">
                            <i class="fas fa-chevron-down"></i>
                            <span>${category.name}</span>
                        </div>
                        <div class="category-channels">
                            ${category.children.map(ch => createChannelElement(ch)).join('')}
                        </div>
                    </div>
                `;
            });
            
            container.innerHTML = html || '<div class="loading">Aucun salon</div>';
        }
        
        function createChannelElement(channel) {
            const icon = channel.type === 'text' ? 'fa-hashtag' : 'fa-volume-up';
            const channelClass = channel.type === 'voice' ? 'voice' : '';
            return `
                <div class="channel-item ${channelClass}" data-channel-id="${channel.id}" onclick="selectChannel('${channel.id}')">
                    <i class="fas ${icon}"></i>
                    <span>${channel.name}</span>
                </div>
            `;
        }
        
        function displayMessages() {
            const container = document.getElementById('messages-list');
            
            if (messages.length === 0) {
                container.innerHTML = '<div style="text-align: center; padding: 40px; color: var(--text-muted);">Aucun message</div>';
                return;
            }
            
            container.innerHTML = messages.reverse().map(msg => createMessageElement(msg)).join('');
        }
        
        function createMessageElement(msg) {
            const time = new Date(msg.timestamp).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
            const isBot = msg.author.bot;
            
            return `
                <div class="message" id="msg-${msg.id}" data-message-id="${msg.id}">
                    <div class="message-avatar">
                        <img src="${msg.author.avatar || 'https://cdn.discordapp.com/embed/avatars/0.png'}" alt="${msg.author.username}">
                    </div>
                    <div class="message-content">
                        <div class="message-header">
                            <span class="message-author">${msg.author.username}</span>
                            ${isBot ? '<span class="message-author bot-tag">BOT</span>' : ''}
                            <span class="message-time">${time}</span>
                        </div>
                        <div class="message-text">${escapeHtml(msg.content)}</div>
                        ${msg.reactions ? createReactionsElement(msg.reactions, msg.id) : ''}
                    </div>
                    <div class="message-actions">
                        <button class="message-action-btn" onclick="addReactionToMessage('${msg.id}')" title="Ajouter une réaction">
                            <i class="far fa-smile"></i>
                        </button>
                        <button class="message-action-btn" onclick="editMessage('${msg.id}')" title="Modifier">
                            <i class="fas fa-pencil-alt"></i>
                        </button>
                        <button class="message-action-btn" onclick="deleteMessage('${msg.id}')" title="Supprimer">
                            <i class="fas fa-trash"></i>
                        </button>
                        <button class="message-action-btn" onclick="copyMessage('${msg.id}')" title="Copier">
                            <i class="fas fa-copy"></i>
                        </button>
                        <button class="message-action-btn" onclick="pinMessage('${msg.id}')" title="Épingler">
                            <i class="fas fa-thumbtack"></i>
                        </button>
                    </div>
                </div>
            `;
        }
        
        function createReactionsElement(reactions, messageId) {
            if (!reactions || reactions.length === 0) return '';
            
            return `
                <div class="reactions-container">
                    ${reactions.map(r => `
                        <div class="reaction ${r.me ? 'me' : ''}" onclick="toggleReaction('${messageId}', '${r.emoji}')">
                            ${r.emoji} <span>${r.count}</span>
                        </div>
                    `).join('')}
                </div>
            `;
        }
        
        function displayMembers() {
            const container = document.getElementById('members-list');
            
            // Trier par statut puis par nom
            members.sort((a, b) => {
                const statusOrder = { online: 0, idle: 1, dnd: 2, offline: 3 };
                if (statusOrder[a.status] !== statusOrder[b.status]) {
                    return statusOrder[a.status] - statusOrder[b.status];
                }
                return a.username.localeCompare(b.username);
            });
            
            container.innerHTML = members.map(member => `
                <div class="member-item" onclick="selectMember('${member.id}')">
                    <div class="member-avatar">
                        <img src="${member.avatar || 'https://cdn.discordapp.com/embed/avatars/0.png'}" alt="${member.username}">
                        <div class="member-status status-${member.status}"></div>
                    </div>
                    <span class="member-name">${member.username}</span>
                    ${member.bot ? '<span class="member-bot-badge">BOT</span>' : ''}
                </div>
            `).join('');
        }
        
        function updateMembersCount() {
            document.getElementById('members-count').textContent = `MEMBRES — ${members.length}`;
        }
        
        // Fonctions de sélection
        function selectServer(serverId) {
            currentServer = serverId;
            const server = servers.find(s => s.id === serverId);
            
            document.getElementById('current-server-name').textContent = server.name;
            document.querySelectorAll('.server-icon').forEach(el => {
                el.classList.remove('active');
                if (el.dataset.serverId === serverId) {
                    el.classList.add('active');
                }
            });
            
            loadChannels(serverId);
            loadMembers(serverId);
            
            // Mettre à jour les sélecteurs dans les modals
            populateMemberSelects();
        }
        
        function selectChannel(channelId) {
            currentChannel = channelId;
            const channel = channels.find(c => c.id === channelId);
            
            document.getElementById('current-channel-name').textContent = channel.name;
            document.getElementById('channel-icon').className = `fas fa-${channel.type === 'text' ? 'hashtag' : 'volume-up'}`;
            
            document.querySelectorAll('.channel-item').forEach(el => {
                el.classList.remove('active');
                if (el.dataset.channelId === channelId) {
                    el.classList.add('active');
                }
            });
            
            loadMessages(channelId);
            socket.emit('join_channel', { channel_id: channelId });
        }
        
        function selectMember(memberId) {
            // Ouvrir menu contextuel pour le membre
            showToast(`Membre sélectionné: ${memberId}`, 'info');
        }
        
        // Fonctions de message
        async function sendMessage() {
            const input = document.getElementById('message-input');
            const content = input.value.trim();
            
            if (!content || !currentChannel) return;
            
            // Animation typing
            socket.emit('typing', { channel_id: currentChannel, typing: true });
            
            try {
                const response = await fetch('/api/send_message', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        channel_id: currentChannel,
                        content: content
                    })
                });
                
                if (response.ok) {
                    input.value = '';
                    adjustTextareaHeight();
                    socket.emit('typing', { channel_id: currentChannel, typing: false });
                    showToast('Message envoyé', 'success');
                } else {
                    throw new Error('Failed to send message');
                }
            } catch (error) {
                showToast('Erreur lors de l\'envoi du message', 'error');
                socket.emit('typing', { channel_id: currentChannel, typing: false });
            }
        }
        
        async function deleteMessage(messageId) {
            if (!confirm('Supprimer ce message ?')) return;
            
            try {
                const response = await fetch('/api/delete_message', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        channel_id: currentChannel,
                        message_id: messageId
                    })
                });
                
                if (response.ok) {
                    showToast('Message supprimé', 'success');
                }
            } catch (error) {
                showToast('Erreur lors de la suppression', 'error');
            }
        }
        
        async function editMessage(messageId) {
            const newContent = prompt('Modifier le message:');
            if (!newContent) return;
            
            try {
                const response = await fetch('/api/edit_message', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        channel_id: currentChannel,
                        message_id: messageId,
                        content: newContent
                    })
                });
                
                if (response.ok) {
                    showToast('Message modifié', 'success');
                }
            } catch (error) {
                showToast('Erreur lors de la modification', 'error');
            }
        }
        
        function copyMessage(messageId) {
            const msg = messages.find(m => m.id === messageId);
            if (msg) {
                navigator.clipboard.writeText(msg.content);
                showToast('Message copié', 'success');
            }
        }
        
        async function pinMessage(messageId) {
            try {
                const response = await fetch('/api/pin_message', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        channel_id: currentChannel,
                        message_id: messageId
                    })
                });
                
                if (response.ok) {
                    showToast('Message épinglé', 'success');
                }
            } catch (error) {
                showToast('Erreur lors de l\'épinglage', 'error');
            }
        }
        
        async function clearMessages() {
            const count = prompt('Combien de messages supprimer ? (max 100)');
            if (!count) return;
            
            try {
                const response = await fetch('/api/clear', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        channel_id: currentChannel,
                        amount: parseInt(count)
                    })
                });
                
                if (response.ok) {
                    showToast(`${count} messages supprimés`, 'success');
                }
            } catch (error) {
                showToast('Erreur lors de la purge', 'error');
            }
        }
        
        function refreshMessages() {
            if (currentChannel) {
                loadMessages(currentChannel);
            }
        }
        
        // Fonctions de réactions
        async function addReactionToMessage(messageId) {
            const emoji = prompt('Entrez l\'emoji:');
            if (!emoji) return;
            
            try {
                const response = await fetch('/api/reaction', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        channel_id: currentChannel,
                        message_id: messageId,
                        emoji: emoji
                    })
                });
                
                if (response.ok) {
                    showToast('Réaction ajoutée', 'success');
                }
            } catch (error) {
                showToast('Erreur lors de l\'ajout de la réaction', 'error');
            }
        }
        
        async function toggleReaction(messageId, emoji) {
            try {
                const response = await fetch('/api/reaction', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        channel_id: currentChannel,
                        message_id: messageId,
                        emoji: emoji
                    })
                });
                
                if (response.ok) {
                    // La réaction sera mise à jour via WebSocket
                }
            } catch (error) {
                showToast('Erreur avec la réaction', 'error');
            }
        }
        
        // Fonctions de modération
        async function executeKick() {
            const memberId = document.getElementById('kick-member').value;
            const reason = document.getElementById('kick-reason').value;
            
            if (!memberId) return;
            
            try {
                const response = await fetch('/api/kick', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        server_id: currentServer,
                        member_id: memberId,
                        reason: reason
                    })
                });
                
                if (response.ok) {
                    showToast('Membre expulsé', 'success');
                    closeModal();
                    loadMembers(currentServer);
                }
            } catch (error) {
                showToast('Erreur lors de l\'expulsion', 'error');
            }
        }
        
        async function executeBan() {
            const memberId = document.getElementById('ban-member').value;
            const reason = document.getElementById('ban-reason').value;
            const deleteDays = document.getElementById('ban-delete-days').checked ? 7 : 0;
            
            if (!memberId) return;
            
            try {
                const response = await fetch('/api/ban', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        server_id: currentServer,
                        member_id: memberId,
                        reason: reason,
                        delete_message_days: deleteDays
                    })
                });
                
                if (response.ok) {
                    showToast('Membre banni', 'success');
                    closeModal();
                    loadMembers(currentServer);
                }
            } catch (error) {
                showToast('Erreur lors du bannissement', 'error');
            }
        }
        
        async function executeRole() {
            const memberId = document.getElementById('role-member').value;
            const roleId = document.getElementById('role-select').value;
            const action = document.getElementById('role-action').value;
            
            try {
                const response = await fetch('/api/role', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        server_id: currentServer,
                        member_id: memberId,
                        role_id: roleId,
                        action: action
                    })
                });
                
                if (response.ok) {
                    showToast('Rôle modifié', 'success');
                    closeModal();
                }
            } catch (error) {
                showToast('Erreur lors de la modification du rôle', 'error');
            }
        }
        
        async function executeTimeout() {
            const memberId = document.getElementById('timeout-member').value;
            const duration = document.getElementById('timeout-duration').value;
            const reason = document.getElementById('timeout-reason').value;
            
            try {
                const response = await fetch('/api/timeout', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        server_id: currentServer,
                        member_id: memberId,
                        duration: parseInt(duration),
                        reason: reason
                    })
                });
                
                if (response.ok) {
                    showToast('Timeout appliqué', 'success');
                    closeModal();
                }
            } catch (error) {
                showToast('Erreur lors du timeout', 'error');
            }
        }
        
        async function executeNickname() {
            const memberId = document.getElementById('nickname-member').value;
            const nickname = document.getElementById('nickname-value').value;
            
            try {
                const response = await fetch('/api/nickname', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        server_id: currentServer,
                        member_id: memberId,
                        nickname: nickname || null
                    })
                });
                
                if (response.ok) {
                    showToast('Surnom modifié', 'success');
                    closeModal();
                }
            } catch (error) {
                showToast('Erreur lors du changement de surnom', 'error');
            }
        }
        
        // Fonctions du bot
        async function changeStatus() {
            const status = document.getElementById('status-select').value;
            
            try {
                const response = await fetch('/api/status', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status: status })
                });
                
                if (response.ok) {
                    updateStatusLed(status);
                    showToast('Statut mis à jour', 'success');
                }
            } catch (error) {
                showToast('Erreur lors du changement de statut', 'error');
            }
        }
        
        function changeStatusFromModal() {
            const status = document.getElementById('modal-status-select').value;
            document.getElementById('status-select').value = status;
            changeStatus();
            closeModal();
        }
        
        function updateStatusLed(status) {
            const led = document.getElementById('bot-status-led');
            led.className = `status-led ${status}`;
        }
        
        async function changeActivity() {
            const type = document.getElementById('activity-type').value;
            const name = document.getElementById('activity-name').value;
            
            try {
                const response = await fetch('/api/activity', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        type: type,
                        name: name
                    })
                });
                
                if (response.ok) {
                    showToast('Activité mise à jour', 'success');
                    closeModal();
                }
            } catch (error) {
                showToast('Erreur lors du changement d\'activité', 'error');
            }
        }
        
        async function changeAvatar() {
            const url = document.getElementById('avatar-url').value;
            const file = document.getElementById('avatar-file').files[0];
            
            let imageData = null;
            
            if (url) {
                imageData = url;
            } else if (file) {
                const reader = new FileReader();
                reader.onload = async (e) => {
                    imageData = e.target.result;
                    await uploadAvatar(imageData);
                };
                reader.readAsDataURL(file);
                return;
            }
            
            if (imageData) {
                await uploadAvatar(imageData);
            }
        }
        
        async function uploadAvatar(imageData) {
            try {
                const response = await fetch('/api/avatar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ avatar: imageData })
                });
                
                if (response.ok) {
                    showToast('Avatar mis à jour', 'success');
                    closeModal();
                }
            } catch (error) {
                showToast('Erreur lors du changement d\'avatar', 'error');
            }
        }
        
        // Fonctions des salons vocaux
        async function joinVoice() {
            if (!currentServer) {
                showToast('Sélectionnez un serveur', 'error');
                return;
            }
            
            const voiceChannels = channels.filter(c => c.type === 'voice');
            if (voiceChannels.length === 0) {
                showToast('Aucun salon vocal disponible', 'error');
                return;
            }
            
            try {
                const response = await fetch('/api/join_voice', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        server_id: currentServer,
                        channel_id: voiceChannels[0].id
                    })
                });
                
                if (response.ok) {
                    showToast('Connecté au salon vocal', 'success');
                }
            } catch (error) {
                showToast('Erreur de connexion vocale', 'error');
            }
        }
        
        async function leaveVoice() {
            if (!currentServer) return;
            
            try {
                const response = await fetch('/api/leave_voice', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ server_id: currentServer })
                });
                
                if (response.ok) {
                    showToast('Déconnecté du salon vocal', 'success');
                }
            } catch (error) {
                showToast('Erreur de déconnexion vocale', 'error');
            }
        }
        
        // Fonctions utilitaires
        function populateMemberSelects() {
            const selects = ['kick-member', 'ban-member', 'role-member', 'timeout-member', 'nickname-member', 'move-member', 'mute-member', 'deafen-member'];
            
            selects.forEach(selectId => {
                const select = document.getElementById(selectId);
                if (select) {
                    select.innerHTML = members.map(m => 
                        `<option value="${m.id}">${m.username} ${m.bot ? '[BOT]' : ''}</option>`
                    ).join('');
                }
            });
        }
        
        function showModal(modalId) {
            document.getElementById('modal-overlay').style.display = 'flex';
            document.querySelectorAll('.modal').forEach(m => m.style.display = 'none');
            document.getElementById(modalId).style.display = 'block';
            
            // Charger les données spécifiques au modal
            if (modalId === 'server-info-modal' && currentServer) {
                loadServerInfo();
            }
        }
        
        function closeModal(event) {
            if (!event || event.target === document.getElementById('modal-overlay')) {
                document.getElementById('modal-overlay').style.display = 'none';
            }
        }
        
        function showToast(message, type = 'info') {
            const container = document.getElementById('toast-container');
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            
            const icon = type === 'success' ? 'fa-check-circle' : 
                        type === 'error' ? 'fa-exclamation-circle' : 
                        'fa-info-circle';
            
            toast.innerHTML = `
                <i class="fas ${icon}"></i>
                <span class="toast-message">${message}</span>
            `;
            
            container.appendChild(toast);
            
            setTimeout(() => {
                toast.style.animation = 'slideInRight 0.3s ease reverse';
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }
        
        function setupMessageInput() {
            const input = document.getElementById('message-input');
            
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                }
            });
            
            input.addEventListener('input', adjustTextareaHeight);
        }
        
        function adjustTextareaHeight() {
            const textarea = document.getElementById('message-input');
            textarea.style.height = 'auto';
            textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
        }
        
        function toggleCategory(header) {
            header.classList.toggle('collapsed');
            const channels = header.nextElementSibling;
            if (channels) {
                channels.style.display = header.classList.contains('collapsed') ? 'none' : 'block';
            }
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        function addMessage(message) {
            messages.unshift(message);
            const container = document.getElementById('messages-list');
            const newMessage = createMessageElement(message);
            container.insertAdjacentHTML('afterbegin', newMessage);
        }
        
        function removeMessage(messageId) {
            const element = document.getElementById(`msg-${messageId}`);
            if (element) {
                element.remove();
            }
            messages = messages.filter(m => m.id !== messageId);
        }
        
        function updateMessage(messageId, newContent) {
            const element = document.getElementById(`msg-${messageId}`);
            if (element) {
                const textElement = element.querySelector('.message-text');
                if (textElement) {
                    textElement.textContent = newContent;
                }
            }
        }
        
        function addReaction(messageId, emoji, userId) {
            // À implémenter: mise à jour des réactions
        }
        
        // Autres fonctions
        async function sendEmbed() {
            const title = document.getElementById('embed-title').value;
            const description = document.getElementById('embed-description').value;
            const color = document.getElementById('embed-color').value;
            
            try {
                const response = await fetch('/api/send_embed', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        channel_id: currentChannel,
                        title: title,
                        description: description,
                        color: color
                    })
                });
                
                if (response.ok) {
                    showToast('Embed envoyé', 'success');
                    closeModal();
                }
            } catch (error) {
                showToast('Erreur lors de l\'envoi de l\'embed', 'error');
            }
        }
        
        async function sendFile() {
            const fileInput = document.getElementById('file-input');
            const file = fileInput.files[0];
            const message = document.getElementById('file-message').value;
            
            if (!file) {
                showToast('Sélectionnez un fichier', 'error');
                return;
            }
            
            const formData = new FormData();
            formData.append('file', file);
            formData.append('channel_id', currentChannel);
            formData.append('content', message);
            
            try {
                const response = await fetch('/api/send_file', {
                    method: 'POST',
                    body: formData
                });
                
                if (response.ok) {
                    showToast('Fichier envoyé', 'success');
                    closeModal();
                }
            } catch (error) {
                showToast('Erreur lors de l\'envoi du fichier', 'error');
            }
        }
        
        async function mentionEveryone() {
            if (!currentChannel) return;
            
            try {
                const response = await fetch('/api/send_message', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        channel_id: currentChannel,
                        content: '@everyone'
                    })
                });
                
                if (response.ok) {
                    showToast('Mention @everyone envoyée', 'success');
                }
            } catch (error) {
                showToast('Erreur lors de la mention', 'error');
            }
        }
        
        async function createChannel() {
            const name = document.getElementById('channel-name').value;
            const type = document.getElementById('channel-type').value;
            const categoryId = document.getElementById('channel-category').value;
            
            try {
                const response = await fetch('/api/create_channel', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        server_id: currentServer,
                        name: name,
                        type: type,
                        category_id: categoryId || null
                    })
                });
                
                if (response.ok) {
                    showToast('Salon créé', 'success');
                    closeModal();
                    loadChannels(currentServer);
                }
            } catch (error) {
                showToast('Erreur lors de la création du salon', 'error');
            }
        }
        
        async function deleteChannel() {
            const channelId = document.getElementById('delete-channel-select').value;
            
            if (!confirm('Voulez-vous vraiment supprimer ce salon ?')) return;
            
            try {
                const response = await fetch('/api/delete_channel', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ channel_id: channelId })
                });
                
                if (response.ok) {
                    showToast('Salon supprimé', 'success');
                    closeModal();
                    loadChannels(currentServer);
                }
            } catch (error) {
                showToast('Erreur lors de la suppression', 'error');
            }
        }
        
        async function loadServerInfo() {
            try {
                const response = await fetch(`/api/server_info/${currentServer}`);
                const info = await response.json();
                
                document.getElementById('server-info-content').innerHTML = `
                    <div class="form-group">
                        <label class="form-label">Nom</label>
                        <div>${info.name}</div>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Propriétaire</label>
                        <div>${info.owner}</div>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Créé le</label>
                        <div>${new Date(info.created_at).toLocaleDateString('fr-FR')}</div>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Membres</label>
                        <div>${info.member_count}</div>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Salons</label>
                        <div>${info.channel_count}</div>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Rôles</label>
                        <div>${info.role_count}</div>
                    </div>
                `;
            } catch (error) {
                console.error('Error loading server info:', error);
            }
        }
        
        async function exportLogs() {
            try {
                const response = await fetch('/api/export_logs');
                const logs = await response.json();
                
                const blob = new Blob([JSON.stringify(logs, null, 2)], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `discord-logs-${Date.now()}.json`;
                a.click();
                
                showToast('Logs exportés', 'success');
            } catch (error) {
                showToast('Erreur lors de l\'export', 'error');
            }
        }
        
        async function executeMove() {
            const memberId = document.getElementById('move-member').value;
            const channelId = document.getElementById('move-channel').value;
            
            try {
                const response = await fetch('/api/move_member', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        server_id: currentServer,
                        member_id: memberId,
                        channel_id: channelId
                    })
                });
                
                if (response.ok) {
                    showToast('Membre déplacé', 'success');
                    closeModal();
                }
            } catch (error) {
                showToast('Erreur lors du déplacement', 'error');
            }
        }
        
        async function executeMute() {
            const memberId = document.getElementById('mute-member').value;
            const action = document.getElementById('mute-action').value;
            
            try {
                const response = await fetch('/api/voice_mute', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        server_id: currentServer,
                        member_id: memberId,
                        mute: action === 'mute'
                    })
                });
                
                if (response.ok) {
                    showToast(action === 'mute' ? 'Membre muté' : 'Membre unmute', 'success');
                    closeModal();
                }
            } catch (error) {
                showToast('Erreur lors du mute', 'error');
            }
        }
        
        async function executeDeafen() {
            const memberId = document.getElementById('deafen-member').value;
            const action = document.getElementById('deafen-action').value;
            
            try {
                const response = await fetch('/api/voice_deafen', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        server_id: currentServer,
                        member_id: memberId,
                        deafen: action === 'deafen'
                    })
                });
                
                if (response.ok) {
                    showToast(action === 'deafen' ? 'Membre deafen' : 'Membre undeafen', 'success');
                    closeModal();
                }
            } catch (error) {
                showToast('Erreur lors du deafen', 'error');
            }
        }
        
        function showEmojiPicker() {
            showToast('Sélecteur d\'emoji à implémenter', 'info');
        }
    </script>
</body>
</html>
'''

# ============================================================
# ROUTES FLASK
# ============================================================
@app.route('/')
def index():
    """Page principale du panel"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/servers')
def api_servers():
    """Retourne la liste des serveurs du bot"""
    servers = []
    for guild in bot.guilds:
        icon_url = str(guild.icon.url) if guild.icon else None
        servers.append({
            'id': str(guild.id),
            'name': guild.name,
            'icon': icon_url,
            'member_count': guild.member_count
        })
    return jsonify(servers)

@app.route('/api/channels/<server_id>')
def api_channels(server_id):
    """Retourne les salons d'un serveur"""
    guild = bot.get_guild(int(server_id))
    if not guild:
        return jsonify({'error': 'Serveur non trouvé'}), 404
    
    channels = []
    for channel in guild.channels:
        if isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel)):
            channels.append({
                'id': str(channel.id),
                'name': channel.name,
                'type': 'text' if isinstance(channel, discord.TextChannel) else 
                       'voice' if isinstance(channel, discord.VoiceChannel) else 'category',
                'position': channel.position,
                'parent_id': str(channel.category_id) if channel.category_id else None
            })
    
    return jsonify(channels)

@app.route('/api/messages/<channel_id>')
def api_messages(channel_id):
    """Retourne les 100 derniers messages d'un salon"""
    # Vérifier le cache
    if channel_id in message_cache and channel_id in cache_timestamps:
        if time.time() - cache_timestamps[channel_id] < CACHE_DURATION:
            return jsonify(message_cache[channel_id])
    
    channel = bot.get_channel(int(channel_id))
    if not channel or not isinstance(channel, discord.TextChannel):
        return jsonify({'error': 'Salon non trouvé'}), 404
    
    async def fetch_messages():
        messages = []
        async for msg in channel.history(limit=100):
            messages.append({
                'id': str(msg.id),
                'content': msg.content,
                'author': {
                    'id': str(msg.author.id),
                    'username': msg.author.name,
                    'avatar': str(msg.author.avatar.url) if msg.author.avatar else None,
                    'bot': msg.author.bot
                },
                'timestamp': msg.created_at.isoformat(),
                'reactions': [
                    {
                        'emoji': str(r.emoji),
                        'count': r.count,
                        'me': r.me
                    } for r in msg.reactions
                ] if msg.reactions else []
            })
        return messages
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    messages = loop.run_until_complete(fetch_messages())
    loop.close()
    
    # Mettre en cache
    message_cache[channel_id] = messages
    cache_timestamps[channel_id] = time.time()
    
    return jsonify(messages)

@app.route('/api/members/<server_id>')
def api_members(server_id):
    """Retourne les membres d'un serveur"""
    guild = bot.get_guild(int(server_id))
    if not guild:
        return jsonify({'error': 'Serveur non trouvé'}), 404
    
    members = []
    for member in guild.members:
        members.append({
            'id': str(member.id),
            'username': member.name,
            'avatar': str(member.avatar.url) if member.avatar else None,
            'status': str(member.status),
            'bot': member.bot,
            'roles': [str(r.id) for r in member.roles[1:]]
        })
    
    return jsonify(members)

@app.route('/api/dms')
def api_dms():
    """Retourne les conversations privées"""
    dms = []
    for dm in bot.private_channels:
        if isinstance(dm, discord.DMChannel):
            dms.append({
                'id': str(dm.id),
                'recipient': {
                    'id': str(dm.recipient.id),
                    'username': dm.recipient.name,
                    'avatar': str(dm.recipient.avatar.url) if dm.recipient.avatar else None
                }
            })
    return jsonify(dms)

@app.route('/api/send_message', methods=['POST'])
def api_send_message():
    """Envoie un message dans un salon"""
    data = request.json
    channel_id = data.get('channel_id')
    content = data.get('content')
    
    if not channel_id or not content:
        return jsonify({'error': 'Données manquantes'}), 400
    
    channel = bot.get_channel(int(channel_id))
    if not channel:
        return jsonify({'error': 'Salon non trouvé'}), 404
    
    async def send():
        msg = await channel.send(content)
        bot_stats['messages_sent'] += 1
        return msg
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    msg = loop.run_until_complete(send())
    loop.close()
    
    # Émettre via WebSocket
    socketio.emit('new_message', {
        'channel_id': channel_id,
        'id': str(msg.id),
        'content': msg.content,
        'author': {
            'id': str(bot.user.id),
            'username': bot.user.name,
            'avatar': str(bot.user.avatar.url) if bot.user.avatar else None,
            'bot': True
        },
        'timestamp': msg.created_at.isoformat()
    })
    
    return jsonify({'success': True, 'message_id': str(msg.id)})

@app.route('/api/delete_message', methods=['POST'])
def api_delete_message():
    """Supprime un message"""
    data = request.json
    channel_id = data.get('channel_id')
    message_id = data.get('message_id')
    
    channel = bot.get_channel(int(channel_id))
    if not channel:
        return jsonify({'error': 'Salon non trouvé'}), 404
    
    async def delete():
        try:
            msg = await channel.fetch_message(int(message_id))
            await msg.delete()
            return True
        except:
            return False
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    success = loop.run_until_complete(delete())
    loop.close()
    
    if success:
        socketio.emit('message_deleted', {
            'channel_id': channel_id,
            'message_id': message_id
        })
        return jsonify({'success': True})
    
    return jsonify({'error': 'Impossible de supprimer le message'}), 400

@app.route('/api/edit_message', methods=['POST'])
def api_edit_message():
    """Modifie un message"""
    data = request.json
    channel_id = data.get('channel_id')
    message_id = data.get('message_id')
    content = data.get('content')
    
    channel = bot.get_channel(int(channel_id))
    if not channel:
        return jsonify({'error': 'Salon non trouvé'}), 404
    
    async def edit():
        try:
            msg = await channel.fetch_message(int(message_id))
            await msg.edit(content=content)
            return True
        except:
            return False
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    success = loop.run_until_complete(edit())
    loop.close()
    
    if success:
        socketio.emit('message_edited', {
            'channel_id': channel_id,
            'message_id': message_id,
            'new_content': content
        })
        return jsonify({'success': True})
    
    return jsonify({'error': 'Impossible de modifier le message'}), 400

@app.route('/api/reaction', methods=['POST'])
def api_reaction():
    """Ajoute une réaction à un message"""
    data = request.json
    channel_id = data.get('channel_id')
    message_id = data.get('message_id')
    emoji = data.get('emoji')
    
    channel = bot.get_channel(int(channel_id))
    if not channel:
        return jsonify({'error': 'Salon non trouvé'}), 404
    
    async def react():
        try:
            msg = await channel.fetch_message(int(message_id))
            await msg.add_reaction(emoji)
            bot_stats['reactions_added'] += 1
            return True
        except:
            return False
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    success = loop.run_until_complete(react())
    loop.close()
    
    if success:
        socketio.emit('reaction_added', {
            'channel_id': channel_id,
            'message_id': message_id,
            'emoji': emoji,
            'user_id': str(bot.user.id)
        })
        return jsonify({'success': True})
    
    return jsonify({'error': 'Impossible d\'ajouter la réaction'}), 400

@app.route('/api/kick', methods=['POST'])
def api_kick():
    """Expulse un membre"""
    data = request.json
    server_id = data.get('server_id')
    member_id = data.get('member_id')
    reason = data.get('reason', '')
    
    guild = bot.get_guild(int(server_id))
    if not guild:
        return jsonify({'error': 'Serveur non trouvé'}), 404
    
    async def kick():
        try:
            member = await guild.fetch_member(int(member_id))
            await member.kick(reason=reason)
            return True
        except:
            return False
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    success = loop.run_until_complete(kick())
    loop.close()
    
    if success:
        socketio.emit('member_update', {'server_id': server_id, 'action': 'kick'})
        return jsonify({'success': True})
    
    return jsonify({'error': 'Impossible d\'expulser le membre'}), 400

@app.route('/api/ban', methods=['POST'])
def api_ban():
    """Bannit un membre"""
    data = request.json
    server_id = data.get('server_id')
    member_id = data.get('member_id')
    reason = data.get('reason', '')
    delete_days = data.get('delete_message_days', 0)
    
    guild = bot.get_guild(int(server_id))
    if not guild:
        return jsonify({'error': 'Serveur non trouvé'}), 404
    
    async def ban():
        try:
            member = await guild.fetch_member(int(member_id))
            await member.ban(reason=reason, delete_message_days=delete_days)
            return True
        except:
            return False
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    success = loop.run_until_complete(ban())
    loop.close()
    
    if success:
        socketio.emit('member_update', {'server_id': server_id, 'action': 'ban'})
        return jsonify({'success': True})
    
    return jsonify({'error': 'Impossible de bannir le membre'}), 400

@app.route('/api/role', methods=['POST'])
def api_role():
    """Gère les rôles d'un membre"""
    data = request.json
    server_id = data.get('server_id')
    member_id = data.get('member_id')
    role_id = data.get('role_id')
    action = data.get('action')
    
    guild = bot.get_guild(int(server_id))
    if not guild:
        return jsonify({'error': 'Serveur non trouvé'}), 404
    
    async def manage_role():
        try:
            member = await guild.fetch_member(int(member_id))
            role = guild.get_role(int(role_id))
            if not role:
                return False
            
            if action == 'add':
                await member.add_roles(role)
            else:
                await member.remove_roles(role)
            return True
        except:
            return False
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    success = loop.run_until_complete(manage_role())
    loop.close()
    
    return jsonify({'success': success})

@app.route('/api/status', methods=['POST'])
def api_status():
    """Change le statut du bot"""
    data = request.json
    status_str = data.get('status', 'online')
    
    status_map = {
        'online': discord.Status.online,
        'idle': discord.Status.idle,
        'dnd': discord.Status.dnd,
        'offline': discord.Status.invisible
    }
    
    status = status_map.get(status_str, discord.Status.online)
    
    async def change():
        await bot.change_presence(status=status)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(change())
    loop.close()
    
    return jsonify({'success': True, 'status': status_str})

@app.route('/api/activity', methods=['POST'])
def api_activity():
    """Change l'activité du bot"""
    data = request.json
    activity_type_str = data.get('type', 'playing')
    name = data.get('name', '')
    
    type_map = {
        'playing': discord.ActivityType.playing,
        'streaming': discord.ActivityType.streaming,
        'listening': discord.ActivityType.listening,
        'watching': discord.ActivityType.watching,
        'competing': discord.ActivityType.competing
    }
    
    activity_type = type_map.get(activity_type_str, discord.ActivityType.playing)
    activity = discord.Activity(type=activity_type, name=name)
    
    async def change():
        await bot.change_presence(activity=activity)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(change())
    loop.close()
    
    return jsonify({'success': True})

@app.route('/api/clear', methods=['POST'])
def api_clear():
    """Purge des messages"""
    data = request.json
    channel_id = data.get('channel_id')
    amount = min(data.get('amount', 10), 100)
    
    channel = bot.get_channel(int(channel_id))
    if not channel or not isinstance(channel, discord.TextChannel):
        return jsonify({'error': 'Salon non trouvé'}), 404
    
    async def purge():
        deleted = await channel.purge(limit=amount)
        return len(deleted)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    count = loop.run_until_complete(purge())
    loop.close()
    
    return jsonify({'success': True, 'deleted': count})

@app.route('/api/stats')
def api_stats():
    """Retourne les statistiques du bot"""
    uptime = datetime.now() - bot_stats['start_time']
    return jsonify({
        'servers': len(bot.guilds),
        'users': sum(g.member_count for g in bot.guilds),
        'messages_sent': bot_stats['messages_sent'],
        'commands_used': bot_stats['commands_used'],
        'reactions_added': bot_stats['reactions_added'],
        'uptime': str(uptime)
    })

@app.route('/api/join_voice', methods=['POST'])
def api_join_voice():
    """Rejoint un salon vocal"""
    data = request.json
    server_id = data.get('server_id')
    channel_id = data.get('channel_id')
    
    guild = bot.get_guild(int(server_id))
    if not guild:
        return jsonify({'error': 'Serveur non trouvé'}), 404
    
    channel = guild.get_channel(int(channel_id))
    if not channel or not isinstance(channel, discord.VoiceChannel):
        return jsonify({'error': 'Salon vocal non trouvé'}), 404
    
    async def join():
        try:
            if guild.voice_client:
                await guild.voice_client.move_to(channel)
            else:
                await channel.connect()
            return True
        except:
            return False
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    success = loop.run_until_complete(join())
    loop.close()
    
    return jsonify({'success': success})

@app.route('/api/leave_voice', methods=['POST'])
def api_leave_voice():
    """Quitte un salon vocal"""
    data = request.json
    server_id = data.get('server_id')
    
    guild = bot.get_guild(int(server_id))
    if not guild:
        return jsonify({'error': 'Serveur non trouvé'}), 404
    
    async def leave():
        if guild.voice_client:
            await guild.voice_client.disconnect()
            return True
        return False
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    success = loop.run_until_complete(leave())
    loop.close()
    
    return jsonify({'success': success})

# ============================================================
# ÉVÉNEMENTS DISCORD
# ============================================================
@bot.event
async def on_ready():
    """Bot prêt"""
    logger.info(f'✅ Bot connecté en tant que {bot.user}')
    logger.info(f'📊 Connecté à {len(bot.guilds)} serveurs')
    
    # Statut initial
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Activity(type=discord.ActivityType.playing, name="Panel Discord")
    )
    
    socketio.emit('bot_ready', {'username': str(bot.user), 'id': str(bot.user.id)})

@bot.event
async def on_message(message):
    """Message reçu"""
    if message.author == bot.user:
        bot_stats['messages_sent'] += 1
    
    # Émettre via WebSocket
    socketio.emit('new_message', {
        'channel_id': str(message.channel.id),
        'id': str(message.id),
        'content': message.content,
        'author': {
            'id': str(message.author.id),
            'username': message.author.name,
            'avatar': str(message.author.avatar.url) if message.author.avatar else None,
            'bot': message.author.bot
        },
        'timestamp': message.created_at.isoformat()
    })
    
    await bot.process_commands(message)

@bot.event
async def on_typing(channel, user, when):
    """Indicateur de typing"""
    socketio.emit('bot_typing', {
        'channel_id': str(channel.id),
        'user': user.name,
        'typing': True
    })
    
    await asyncio.sleep(5)
    socketio.emit('bot_typing', {
        'channel_id': str(channel.id),
        'user': user.name,
        'typing': False
    })

@bot.event
async def on_member_join(member):
    """Membre rejoint"""
    socketio.emit('member_update', {
        'server_id': str(member.guild.id),
        'action': 'join',
        'member': str(member.id)
    })

@bot.event
async def on_member_remove(member):
    """Membre quitte"""
    socketio.emit('member_update', {
        'server_id': str(member.guild.id),
        'action': 'leave',
        'member': str(member.id)
    })

@bot.event
async def on_member_update(before, after):
    """Mise à jour d'un membre"""
    socketio.emit('member_update', {
        'server_id': str(after.guild.id),
        'action': 'update',
        'member': str(after.id)
    })

@bot.event
async def on_message_delete(message):
    """Message supprimé"""
    socketio.emit('message_deleted', {
        'channel_id': str(message.channel.id),
        'message_id': str(message.id)
    })

@bot.event
async def on_message_edit(before, after):
    """Message modifié"""
    socketio.emit('message_edited', {
        'channel_id': str(after.channel.id),
        'message_id': str(after.id),
        'new_content': after.content
    })

@bot.event
async def on_reaction_add(reaction, user):
    """Réaction ajoutée"""
    socketio.emit('reaction_added', {
        'channel_id': str(reaction.message.channel.id),
        'message_id': str(reaction.message.id),
        'emoji': str(reaction.emoji),
        'user_id': str(user.id)
    })

# ============================================================
# SOCKET.IO ÉVÉNEMENTS
# ============================================================
@socketio.on('connect')
def handle_connect():
    """Client connecté"""
    logger.info('Client WebSocket connecté')
    emit('connected', {'message': 'Connecté au serveur'})

@socketio.on('disconnect')
def handle_disconnect():
    """Client déconnecté"""
    logger.info('Client WebSocket déconnecté')

@socketio.on('join_channel')
def handle_join_channel(data):
    """Rejoint une room pour un salon"""
    channel_id = data.get('channel_id')
    if channel_id:
        join_room(channel_id)
        logger.info(f'Client a rejoint le salon {channel_id}')

@socketio.on('typing')
def handle_typing(data):
    """Gère l'événement typing"""
    channel_id = data.get('channel_id')
    typing = data.get('typing', False)
    
    if channel_id:
        emit('bot_typing', {
            'channel_id': channel_id,
            'user': bot.user.name,
            'typing': typing
        }, room=channel_id)

# ============================================================
# DÉMARRAGE DU BOT ET DU SERVEUR WEB
# ============================================================
def run_bot():
    """Démarre le bot Discord dans un thread séparé"""
    try:
        bot.run(TOKEN)
    except Exception as e:
        logger.error(f"Erreur bot Discord: {e}")
        traceback.print_exc()

def run_web():
    """Démarre le serveur web Flask"""
    try:
        socketio.run(app, host='0.0.0.0', port=PORT, debug=False, allow_unsafe_werkzeug=True)
    except Exception as e:
        logger.error(f"Erreur serveur web: {e}")
        traceback.print_exc()

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 DÉMARRAGE DU PANEL DE CONTRÔLE DISCORD")
    print("=" * 60)
    print(f"📡 Token Discord: {'✅ Configuré' if TOKEN else '❌ Manquant'}")
    print(f"🌐 Port web: {PORT}")
    print("=" * 60)
    
    # Démarrer le bot Discord dans un thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Attendre que le bot soit prêt
    time.sleep(3)
    
    # Démarrer le serveur web dans le thread principal
    print(f"🌍 Panel web accessible sur http://0.0.0.0:{PORT}")
    print("=" * 60)
    
    run_web()
