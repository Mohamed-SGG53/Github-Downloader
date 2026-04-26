import os
import sys
import re
import json
import threading
import webview
import requests
from urllib.parse import unquote

# --- Backend Logic Class ---

class Api:
    def __init__(self):
        self.window = None

    def parse_github_url(self, url):
        pattern = r'github\.com/([^/]+)/([^/]+)(?:/(tree|blob)/([^/]+)(?:/(.*))?)?'
        match = re.search(pattern, url)
        if not match:
            return None
        
        owner = match.group(1)
        repo = match.group(2)
        branch = match.group(4)
        path = match.group(5) if match.group(5) else ''
        
        if repo.endswith('.git'):
            repo = repo[:-4]
            
        return {'owner': owner, 'repo': repo, 'branch': branch, 'path': path}

    def get_headers(self, token=None):
        headers = {'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'PyWebView-Downloader'}
        if token:
            headers['Authorization'] = f'token {token}'
        return headers

    def check_repo(self, url, token=None):
        parsed = self.parse_github_url(url)
        if not parsed:
            return {'error': 'Invalid URL format', 'valid': False}

        try:
            api_url = f"https://api.github.com/repos/{parsed['owner']}/{parsed['repo']}"
            response = requests.get(api_url, headers=self.get_headers(token))
            
            if response.status_code == 404:
                if token:
                    return {'error': 'Repository not found or no access with provided token', 'needs_token': False, 'valid': False}
                return {'error': 'Repository not found or private', 'needs_token': True, 'valid': False}
            
            if response.status_code == 401:
                return {'error': 'Invalid Token', 'needs_token': True, 'valid': False}
            if response.status_code == 403:
                return {'error': 'API Rate Limit Exceeded. Please use a Token.', 'needs_token': False, 'valid': False}
            if response.status_code != 200:
                return {'error': f'Server Error: {response.status_code}', 'needs_token': False, 'valid': False}
            
            data = response.json()
            return {
                'valid': True,
                'name': data['name'],
                'owner': data['owner']['login'],
                'stars': data['stargazers_count'],
                'forks': data['forks_count'],
                'issues': data['open_issues_count'],
                'default_branch': data['default_branch'],
                'private': data['private']
            }
        except Exception as e:
            return {'error': 'Network Connection Failed', 'needs_token': False, 'valid': False}

    def get_branches(self, url, token=None):
        parsed = self.parse_github_url(url)
        if not parsed: return []
        
        try:
            api_url = f"https://api.github.com/repos/{parsed['owner']}/{parsed['repo']}/branches?per_page=100"
            response = requests.get(api_url, headers=self.get_headers(token))
            if response.status_code != 200: return []
            return [b['name'] for b in response.json()]
        except:
            return []

    def sanitize_name(self, name):
        name = unquote(name) 
        name = re.sub(r'[\\/*?:"<>|]', "", name) 
        return name.strip()

    def select_folder(self):
        result = self.window.create_file_dialog(webview.FOLDER_DIALOG)
        if result and len(result) > 0:
            return result[0]
        return None

    def start_download(self, url, token, selected_branch, save_path):
        parsed = self.parse_github_url(url)
        if not parsed:
            self.emit_status('error', 'Invalid Input', 'Invalid URL')
            return

        repo_info = self.check_repo(url, token)
        if not repo_info.get('valid'):
            msg = 'Please enter a valid Token for this repository.'
            if 'not found' in repo_info.get('error', '').lower():
                msg = 'Repository not found or does not exist.'
            self.emit_status('error', 'Access Denied', msg)
            return
            
        branch = selected_branch or parsed['branch'] or repo_info.get('default_branch', 'main')
        
        if parsed['path']:
            folder_name = self.sanitize_name(parsed['path'].split('/')[-1])
        else:
            folder_name = self.sanitize_name(parsed['repo'])
            
        target_path = os.path.join(save_path, folder_name)

        try:
            self.emit_status('info', 'Preparing', 'Fetching file list...')
            
            tree_url = f"https://api.github.com/repos/{parsed['owner']}/{parsed['repo']}/git/trees/{branch}?recursive=1"
            tree_resp = requests.get(tree_url, headers=self.get_headers(token))
            
            if tree_resp.status_code != 200:
                raise Exception("Failed to fetch file tree")
                
            tree_data = tree_resp.json()
            files = tree_data.get('tree', [])
            
            prefix = parsed['path'].rstrip('/') + '/' if parsed['path'] else ''
            if prefix:
                files = [f for f in files if f['path'].startswith(prefix)]

            display_files = [
                {'name': f['path'].split('/')[-1], 'path': f['path'], 'type': f['type']} 
                for f in files[:50] 
            ]
            self.emit_tree(display_files, folder_name)

            file_list = [f for f in files if f['type'] == 'blob']
            total_files = len(file_list)
            
            if total_files == 0:
                self.emit_status('error', 'Empty Repo', 'No files found to download')
                return

            os.makedirs(target_path, exist_ok=True)
            self.emit_progress(0, f'Downloading 0/{total_files} files...')

            for i, item in enumerate(file_list):
                relative_path = item['path']
                if prefix:
                    relative_path = relative_path[len(prefix):]
                
                path_parts = relative_path.split('/')
                clean_path = os.path.join(target_path, *path_parts)
                
                raw_url = f"https://raw.githubusercontent.com/{parsed['owner']}/{parsed['repo']}/{branch}/{item['path']}"
                
                self.emit_progress(((i+1)/total_files)*100, f'Downloading: {path_parts[-1]}')
                
                file_resp = requests.get(raw_url, headers=self.get_headers(token))
                if file_resp.status_code == 200:
                    os.makedirs(os.path.dirname(clean_path), exist_ok=True)
                    with open(clean_path, 'wb') as f:
                        f.write(file_resp.content)

            self.emit_progress(100, 'Complete!')
            self.emit_status('success', 'Success', f'Downloaded {total_files} files to {folder_name}')

        except Exception as e:
            self.emit_status('error', 'Download Failed', str(e))

    def emit_status(self, type_, title, message):
        self.window.evaluate_js(f"window.py_status('{type_}', '{title}', '{message}')")

    def emit_progress(self, percent, text):
        self.window.evaluate_js(f"window.py_progress({percent}, '{text}')")

    def emit_tree(self, files, name):
        json_data = json.dumps(files)
        safe_json = json_data.replace("'", "\\'") 
        self.window.evaluate_js(f"window.py_tree({safe_json}, '{name}')")

# --- HTML Template (English UI) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GitHub Downloader</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Space+Grotesk:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #0f1014; --bg-secondary: #1a1b23; --fg: #e8e8ed;
            --muted: #6b6b7b; --accent: #00d4aa; --accent-dim: #00d4aa22;
            --card: rgba(25, 26, 35, 0.85); --border: #2a2a3a; --error: #ff4757;
            --warning: #ffa502; --info: #3498db; --success: #00d4aa;
        }
        * { box-sizing: border-box; }
        body { font-family: 'Space Grotesk', sans-serif; background: var(--bg); color: var(--fg); min-height: 100vh; overflow-x: hidden; }

        /* --- OUT OF THE BOX BACKGROUND: GEOMETRIC VITALITY --- */
        .bg-container {
            position: fixed;
            top: 0; left: 0; width: 100%; height: 100%;
            background: radial-gradient(circle at 50% 50%, #1a1b23 0%, #0f1014 100%);
            z-index: -1;
            overflow: hidden;
            /* Perspective for 3D rotation */
            perspective: 1000px; 
        }

        /* 1. Light Leaks (Atmosphere) */
        .light-leak {
            position: absolute;
            width: 60%;
            height: 200%;
            background: linear-gradient(90deg, transparent, rgba(0, 212, 170, 0.03), transparent);
            transform: rotate(25deg);
            animation: leakMove 20s linear infinite;
        }
        .light-leak.l2 {
            background: linear-gradient(90deg, transparent, rgba(124, 58, 237, 0.04), transparent);
            animation-duration: 25s;
            animation-delay: -10s;
        }
        @keyframes leakMove { 0% { transform: translateX(-100%) rotate(25deg); } 100% { transform: translateX(100%) rotate(25deg); } }

        /* 2. Geometric Shapes (Holographic) */
        .shape {
            position: absolute;
            opacity: 0.4;
            border: 2px solid;
            /* 3D rotation capability */
            transform-style: preserve-3d;
        }

        /* Shape 1: Triangle */
        .shape-1 {
            width: 100px; height: 100px;
            top: 15%; left: 10%;
            background: transparent;
            border: none;
            border-right: 2px solid #00d4aa;
            border-bottom: 2px solid #00d4aa;
            transform: rotate(45deg);
            animation: tRotate 20s linear infinite, float 10s ease-in-out infinite;
        }

        /* Shape 2: Ring */
        .shape-2 {
            width: 250px; height: 250px;
            bottom: 10%; right: 10%;
            border: 2px solid rgba(124, 58, 237, 0.6);
            border-radius: 50%;
            box-shadow: 0 0 20px rgba(124, 58, 237, 0.1);
            animation: spin360 30s linear infinite;
        }

        /* Shape 3: Hexagon (Simulated with clip-path) */
        .shape-3 {
            width: 150px; height: 150px;
            top: 60%; left: 60%;
            background: rgba(56, 189, 248, 0.05);
            border: none; /* Remove border, use clip-path */
            clip-path: polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%);
            /* Add border using a pseudo-element or box-shadow trick, simpler: outline inside clip-path not possible easily, so use shadow */
            box-shadow: 0 0 15px rgba(56, 189, 248, 0.15);
            animation: drift 15s ease-in-out infinite, scalePulse 8s ease-in-out infinite;
        }

        /* Shape 4: Diamond */
        .shape-4 {
            width: 80px; height: 80px;
            top: 40%; right: 25%;
            background: rgba(244, 114, 182, 0.1);
            border: 2px solid rgba(244, 114, 182, 0.4);
            transform: rotate(45deg);
            animation: tRotate 15s linear infinite reverse; /* Rotate opposite direction */
        }

        /* Keyframes */
        @keyframes tRotate { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        @keyframes spin360 { 0% { transform: rotate(0deg) scale(1); } 50% { transform: rotate(180deg) scale(1.1); } 100% { transform: rotate(360deg) scale(1); } }
        @keyframes float { 0%, 100% { transform: translateY(0) rotate(45deg); } 50% { transform: translateY(-30px) rotate(45deg); } }
        @keyframes drift { 0%, 100% { transform: translate(0, 0); } 50% { transform: translate(40px, -40px); } }
        @keyframes scalePulse { 0%, 100% { opacity: 0.3; } 50% { opacity: 0.6; } }

        /* --- END BACKGROUND --- */

        .main-container { position: relative; z-index: 1; max-width: 900px; margin: 0 auto; padding: 2rem; min-height: 100vh; }
        .header { text-align: center; margin-bottom: 3rem; animation: fadeInUp 0.8s ease-out; }
        .logo { display: inline-flex; align-items: center; gap: 1rem; margin-bottom: 1.5rem; }
        .logo-icon { width: 56px; height: 56px; background: linear-gradient(135deg, var(--accent), #7c3aed); border-radius: 16px; display: flex; align-items: center; justify-content: center; animation: pulse 3s ease-in-out infinite; }
        @keyframes pulse { 0%, 100% { box-shadow: 0 0 0 0 var(--accent-dim); } 50% { box-shadow: 0 0 30px 10px var(--accent-dim); } }
        .title { font-size: 2.5rem; font-weight: 700; letter-spacing: -0.02em; background: linear-gradient(135deg, var(--fg) 0%, var(--muted) 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
        .subtitle { color: var(--muted); font-size: 1.1rem; font-weight: 400; }
        
        .card { 
            background: var(--card); 
            backdrop-filter: blur(20px); 
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.08); 
            border-radius: 24px; 
            overflow: hidden; 
            animation: fadeInUp 0.8s ease-out 0.2s backwards; 
            box-shadow: 0 20px 50px -20px rgba(0, 0, 0, 0.5); 
        }
        
        .tabs { display: flex; border-bottom: 1px solid var(--border); background: rgba(0,0,0,0.2); }
        .tab { flex: 1; padding: 1.25rem 1.5rem; font-size: 1rem; font-weight: 500; color: var(--muted); background: transparent; border: none; cursor: pointer; position: relative; transition: all 0.3s ease; display: flex; align-items: center; justify-content: center; gap: 0.5rem; }
        .tab:hover { color: var(--fg); background: rgba(255, 255, 255, 0.02); }
        .tab.active { color: var(--accent); background: rgba(0, 255, 204, 0.05); }
        .tab.active::after { content: ''; position: absolute; bottom: -1px; left: 0; right: 0; height: 2px; background: var(--accent); }
        .tab-icon { width: 20px; height: 20px; }
        .tab-content { display: none; padding: 2rem; animation: fadeIn 0.3s ease-out; }
        .tab-content.active { display: block; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes fadeInUp { from { opacity: 0; transform: translateY(30px); } to { opacity: 1; transform: translateY(0); } }
        .form-group { margin-bottom: 1.5rem; }
        .form-label { display: block; font-size: 0.9rem; font-weight: 500; color: var(--muted); margin-bottom: 0.75rem; }
        .form-input { width: 100%; padding: 1rem 1.25rem; font-size: 0.95rem; font-family: 'JetBrains Mono', monospace; background: rgba(0, 0, 0, 0.3); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; color: var(--fg); transition: all 0.3s ease; }
        .form-input:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-dim); background: rgba(0, 0, 0, 0.5); }
        .form-input::placeholder { color: var(--muted); opacity: 0.6; }
        .input-hint { font-size: 0.8rem; color: var(--muted); margin-top: 0.5rem; font-family: 'JetBrains Mono', monospace; }
        .input-hint a { color: var(--accent); text-decoration: none; }
        .input-hint a:hover { text-decoration: underline; }
        .url-type-indicator { display: none; align-items: center; gap: 0.5rem; padding: 0.75rem 1rem; background: rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; margin-top: 0.75rem; font-size: 0.85rem; }
        .url-type-indicator.show { display: flex; }
        .url-type-indicator.repo { border-color: var(--info); background: rgba(52, 152, 219, 0.1); }
        .url-type-indicator.directory { border-color: var(--accent); background: rgba(0, 212, 170, 0.1); }
        .url-type-dot { width: 8px; height: 8px; border-radius: 50%; }
        .url-type-indicator.repo .url-type-dot { background: var(--info); }
        .url-type-indicator.directory .url-type-dot { background: var(--accent); }
        .url-type-text { color: var(--fg); }
        .url-type-badge { font-size: 0.75rem; padding: 0.25rem 0.5rem; border-radius: 4px; font-weight: 600; }
        .url-type-indicator.repo .url-type-badge { background: var(--info); color: var(--bg); }
        .url-type-indicator.directory .url-type-badge { background: var(--accent); color: var(--bg); }
        
        .branch-selector { display: none; margin-top: 12px; margin-bottom: 10px; padding: 1rem; background: rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; }
        
        .branch-selector.show { display: block; }
        .branch-selector-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem; }
        .branch-selector-title { font-size: 0.85rem; color: var(--muted); }
        .branch-selector-count { font-size: 0.75rem; color: var(--accent); font-family: 'JetBrains Mono', monospace; }
        .branch-list { display: flex; flex-wrap: wrap; gap: 0.5rem; max-height: 120px; overflow-y: auto; }
        .branch-item { padding: 0.5rem 1rem; font-size: 0.85rem; font-family: 'JetBrains Mono', monospace; background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; color: var(--fg); cursor: pointer; transition: all 0.2s ease; }
        .branch-item:hover { border-color: var(--accent); color: var(--accent); }
        .branch-item.active { background: var(--accent); color: var(--bg); border-color: var(--accent); }
        .btn { display: inline-flex; align-items: center; justify-content: center; gap: 0.5rem; padding: 1rem 2rem; font-size: 1rem; font-weight: 600; border: none; border-radius: 12px; cursor: pointer; transition: all 0.3s ease; position: relative; overflow: hidden; }
        .btn-primary { background: linear-gradient(135deg, var(--accent), #00b894); color: var(--bg); width: 100%; }
        .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 10px 30px -10px var(--accent); }
        .btn-primary:active { transform: translateY(0); }
        .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
        .btn-icon { width: 20px; height: 20px; }
        .spinner { width: 20px; height: 20px; border: 2px solid transparent; border-top-color: currentColor; border-radius: 50%; animation: spin 0.8s linear infinite; flex-shrink: 0; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .status { padding: 1rem 1.25rem; border-radius: 12px; margin-top: 1.5rem; display: none; align-items: flex-start; gap: 0.75rem; animation: slideIn 0.3s ease-out; backdrop-filter: blur(10px); }
        @keyframes slideIn { from { opacity: 0; transform: translateX(-10px); } to { opacity: 1; transform: translateX(0); } }
        .status.show { display: flex; }
        .status.error { background: rgba(255, 71, 87, 0.1); border: 1px solid rgba(255, 71, 87, 0.3); color: var(--error); }
        .status.warning { background: rgba(255, 165, 2, 0.1); border: 1px solid rgba(255, 165, 2, 0.3); color: var(--warning); }
        .status.success { background: rgba(0, 212, 170, 0.1); border: 1px solid rgba(0, 212, 170, 0.3); color: var(--accent); }
        .status.info { background: rgba(52, 152, 219, 0.1); border: 1px solid rgba(52, 152, 219, 0.3); color: var(--info); }
        .status-icon { width: 20px; height: 20px; flex-shrink: 0; margin-top: 2px; }
        .status-content { flex: 1; }
        .status-title { font-weight: 600; margin-bottom: 0.25rem; }
        .status-message { font-size: 0.9rem; opacity: 0.9; }
        .file-tree { background: rgba(0, 0, 0, 0.3); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; margin-top: 1.5rem; max-height: 400px; overflow-y: auto; display: none; }
        .file-tree.show { display: block; animation: fadeIn 0.3s ease-out; }
        .file-tree-header { padding: 1rem 1.25rem; border-bottom: 1px solid rgba(255,255,255,0.08); font-weight: 600; display: flex; align-items: center; justify-content: space-between; position: sticky; top: 0; background: rgba(15, 16, 20, 0.9); z-index: 1; }
        .file-count { font-size: 0.85rem; color: var(--muted); font-weight: 400; }
        .file-item { display: flex; align-items: center; gap: 0.75rem; padding: 0.75rem 1.25rem; border-bottom: 1px solid rgba(255,255,255,0.05); transition: background 0.2s ease; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; }
        .file-item:last-child { border-bottom: none; }
        .file-item:hover { background: rgba(255, 255, 255, 0.03); }
        .file-item.folder { color: var(--accent); }
        .file-icon { width: 18px; height: 18px; flex-shrink: 0; opacity: 0.7; }
        .file-item.folder .file-icon { opacity: 1; }
        .progress-container { margin-top: 1.5rem; display: none; }
        .progress-container.show { display: block; }
        .progress-header { display: flex; justify-content: space-between; margin-bottom: 0.5rem; font-size: 0.9rem; }
        .progress-text { color: var(--muted); }
        .progress-percent { color: var(--accent); font-weight: 600; font-family: 'JetBrains Mono', monospace; }
        .progress-bar { height: 8px; background: rgba(0,0,0,0.5); border-radius: 4px; overflow: hidden; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, var(--accent), #7c3aed); border-radius: 4px; transition: width 0.3s ease; position: relative; }
        .progress-fill::after { content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent); animation: shimmer 1.5s infinite; }
        @keyframes shimmer { 0% { transform: translateX(-100%); } 100% { transform: translateX(100%); } }
        .repo-info { display: none; background: rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 1.25rem; margin-top: 1rem; }
        .repo-info.show { display: block; }
        .repo-info-header { display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem; }
        .repo-avatar { width: 40px; height: 40px; border-radius: 10px; background: rgba(255,255,255,0.05); display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 1.1rem; color: var(--accent); }
        .repo-name { font-size: 1.1rem; font-weight: 600; }
        .repo-owner { font-size: 0.85rem; color: var(--muted); }
        .repo-stats { display: flex; gap: 1.5rem; flex-wrap: wrap; }
        .repo-stat { display: flex; align-items: center; gap: 0.4rem; font-size: 0.85rem; color: var(--muted); }
        .repo-stat-icon { width: 16px; height: 16px; opacity: 0.7; }
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }
    </style>
</head>
<body>
    <div class="bg-container">
        <!-- Light Leaks for Atmosphere -->
        <div class="light-leak"></div>
        <div class="light-leak l2"></div>
        
        <!-- Geometric Shapes -->
        <div class="shape shape-1"></div> <!-- Triangle -->
        <div class="shape shape-2"></div> <!-- Ring -->
        <div class="shape shape-3"></div> <!-- Hexagon -->
        <div class="shape shape-4"></div> <!-- Diamond -->
    </div>

    <div class="main-container">
        <header class="header">
            <div class="logo">
                <div class="logo-icon">
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                        <polyline points="7 10 12 15 17 10"/>
                        <line x1="12" y1="15" x2="12" y2="3"/>
                    </svg>
                </div>
            </div>
            <h1 class="title">GitHub Downloader</h1>
            <p class="subtitle">Download full repositories or specific directories - Public or Private</p>
        </header>

        <div class="card">
            <div class="tabs">
                <button class="tab active" data-tab="public" onclick="switchTab('public')">
                    <svg class="tab-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/>
                        <line x1="2" y1="12" x2="22" y2="12"/>
                        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
                    </svg>
                    Public Repository
                </button>
                <button class="tab" data-tab="private" onclick="switchTab('private')">
                    <svg class="tab-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                        <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                    </svg>
                    Private Repository
                </button>
            </div>

            <!-- Public Tab -->
            <div class="tab-content active" id="public-tab">
                <form id="public-form" onsubmit="handlePublicSubmit(event)">
                    <div class="form-group">
                        <label class="form-label">GitHub URL</label>
                        <input type="text" class="form-input" id="public-url" placeholder="https://github.com/username/repo" autocomplete="off" oninput="handleUrlInput('public', this.value)">
                        <div class="url-type-indicator" id="public-url-type">
                            <div class="url-type-dot"></div>
                            <span class="url-type-text"></span>
                            <span class="url-type-badge"></span>
                        </div>
                        <p class="input-hint">Repo: github.com/user/repo | Directory: github.com/user/repo/tree/branch/path</p>
                    </div>
                    <div class="repo-info" id="public-repo-info">
                        <div class="repo-info-header">
                            <div class="repo-avatar" id="public-avatar"></div>
                            <div>
                                <div class="repo-name" id="public-repo-name"></div>
                                <div class="repo-owner" id="public-repo-owner"></div>
                            </div>
                        </div>
                        <div class="repo-stats">
                            <div class="repo-stat"><svg class="repo-stat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg><span id="public-stars">0</span></div>
                            <div class="repo-stat"><svg class="repo-stat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 18V4a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2z"/><path d="M17 21H7a2 2 0 0 1-2-2V5"/></svg><span id="public-forks">0</span></div>
                            <div class="repo-stat"><svg class="repo-stat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg><span id="public-issues">0</span></div>
                        </div>
                    </div>
                    <div class="branch-selector" id="public-branch-selector">
                        <div class="branch-selector-header">
                            <span class="branch-selector-title">Select Branch:</span>
                            <span class="branch-selector-count" id="public-branch-count"></span>
                        </div>
                        <div class="branch-list" id="public-branch-list"></div>
                    </div>
                    <button type="submit" class="btn btn-primary" id="public-btn">
                        <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                        <span>Download</span>
                    </button>
                </form>
                <div class="status" id="public-status">
                    <svg class="status-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                    <div class="status-content"><div class="status-title"></div><div class="status-message"></div></div>
                </div>
                <div class="file-tree" id="public-tree"></div>
                <div class="progress-container" id="public-progress">
                    <div class="progress-header"><span class="progress-text">Downloading...</span><span class="progress-percent">0%</span></div>
                    <div class="progress-bar"><div class="progress-fill" style="width: 0%"></div></div>
                </div>
            </div>

            <!-- Private Tab -->
            <div class="tab-content" id="private-tab">
                <form id="private-form" onsubmit="handlePrivateSubmit(event)">
                    <div class="form-group">
                        <label class="form-label">GitHub URL (Make Sure This Repo Is Existing)</label>
                        <input type="text" class="form-input" id="private-url" placeholder="https://github.com/username/repo" autocomplete="off" oninput="handleUrlInput('private', this.value)">
                        <div class="url-type-indicator" id="private-url-type">
                            <div class="url-type-dot"></div>
                            <span class="url-type-text"></span>
                            <span class="url-type-badge"></span>
                        </div>
                        <p class="input-hint">Repo: github.com/user/repo | Directory: github.com/user/repo/tree/branch/path</p>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Personal Access Token</label>
                        <input type="password" class="form-input" id="private-token" placeholder="ghp_xxxxxxxxxxxxxxxxxxxx" autocomplete="off">
                        <p class="input-hint">Create a token at <a href="#" onclick="openLink('https://github.com/settings/tokens/new')">GitHub Settings</a> with 'repo' permissions</p>
                    </div>
                    
                    <button type="submit" class="btn btn-primary" id="private-btn">
                        <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                        <span>Download</span>
                    </button>
                </form>
                <div class="status" id="private-status">
                    <svg class="status-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                    <div class="status-content"><div class="status-title"></div><div class="status-message"></div></div>
                </div>
                <div class="file-tree" id="private-tree"></div>
                <div class="progress-container" id="private-progress">
                    <div class="progress-header"><span class="progress-text">Downloading...</span><span class="progress-percent">0%</span></div>
                    <div class="progress-bar"><div class="progress-fill" style="width: 0%"></div></div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentTab = 'public';
        const selectedBranches = { public: null, private: null };
        const repoCache = { public: null, private: null };
        let debounceTimer = null;
        let loadingInterval = null;

        async function pyCall(funcName, ...args) {
            if (window.pywebview) return await pywebview.api[funcName](...args);
            console.error('PyWebview API not ready');
            return null;
        }

        function openLink(url) { window.open(url, '_blank'); }

        window.py_status = function(type, title, message) { showStatus(currentTab, type, title, message); };
        window.py_progress = function(percent, text) { updateProgress(currentTab, percent, text); };
        window.py_tree = function(files, name) { renderFileTree(currentTab, files, name, ''); };

        function switchTab(tab) {
            currentTab = tab;
            document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
            document.querySelectorAll('.tab-content').forEach(content => content.classList.toggle('active', content.id === `${tab}-tab`));
            hideStatus('public'); hideStatus('private');
        }

        function parseGitHubUrlLocal(url) {
            try {
                const urlObj = new URL(url);
                if (urlObj.hostname !== 'github.com') return null;
                const pathParts = urlObj.pathname.split('/').filter(Boolean);
                if (pathParts.length < 2) return null;
                const owner = pathParts[0], repo = pathParts[1];
                let branch = '', dirPath = '', isFullRepo = true;
                if (pathParts.length > 3 && (pathParts[2] === 'tree' || pathParts[2] === 'blob')) {
                    branch = pathParts[3]; dirPath = pathParts.slice(4).join('/'); isFullRepo = false;
                }
                return { owner, repo, branch, dirPath, isFullRepo };
            } catch (e) { return null; }
        }

        function handleUrlInput(tab, url) {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                processUrlInput(tab, url);
            }, 500);
        }

        async function processUrlInput(tab, url) {
            const parsed = parseGitHubUrlLocal(url);
            const typeIndicator = document.getElementById(`${tab}-url-type`);
            const repoInfo = document.getElementById(`${tab}-repo-info`);
            const branchSelector = document.getElementById(`${tab}-branch-selector`);
            
            if (repoInfo) repoInfo.classList.remove('show');
            if (branchSelector) branchSelector.classList.remove('show');
            repoCache[tab] = null;
            
            if (!parsed) {
                typeIndicator.classList.remove('show');
                return;
            }

            typeIndicator.classList.add('show');
            if (parsed.isFullRepo) {
                typeIndicator.className = 'url-type-indicator show repo';
                typeIndicator.querySelector('.url-type-text').textContent = 'Will download entire Repository';
                typeIndicator.querySelector('.url-type-badge').textContent = 'REPO';
            } else {
                typeIndicator.className = 'url-type-indicator show directory';
                typeIndicator.querySelector('.url-type-text').textContent = `Will download: ${parsed.dirPath || 'root'}`;
                typeIndicator.querySelector('.url-type-badge').textContent = 'DIRECTORY';
            }
            
            fetchRepoInfo(tab, parsed);
        }

        async function fetchRepoInfo(tab, parsed) {
            const token = tab === 'private' ? document.getElementById('private-token').value.trim() : null;
            const repoInfo = document.getElementById(`${tab}-repo-info`);
            const branchSelector = document.getElementById(`${tab}-branch-selector`);
            
            try {
                const result = await pyCall('check_repo', `https://github.com/${parsed.owner}/${parsed.repo}`, token);
                if (!result) return;

                if (!result.valid) {
                    if (result.needs_token && tab === 'public') {
                        showStatus('public', 'warning', 'Private Repository', 'Switching To Private Tab...');
                        setTimeout(() => {
                            switchTab('private');
                            document.getElementById('private-url').value = document.getElementById('public-url').value;
                            handleUrlInput('private', document.getElementById('private-url').value);
                        }, 1000);
                    } else if (result.needs_token && tab === 'private') {
                         showStatus(tab, 'error', 'Access Denied', 'Please enter a valid Token for this repository.');
                    } else {
                        let title = "Connection Error";
                        if(result.error && result.error.includes('Rate Limit')) title = "Rate Limit Exceeded";
                        else if(result.error && result.error.includes('not found')) title = "Not Found";
                        else if(result.error && result.error.includes('Network')) title = "Network Error";
                        
                        showStatus(tab, 'error', title, result.error || 'Unknown error occurred.');
                    }
                    return;
                }

                if (result.private === false) {
                    if (tab === 'public') {
                        repoCache[tab] = result;
                        document.getElementById(`${tab}-avatar`).textContent = result.owner.charAt(0).toUpperCase();
                        document.getElementById(`${tab}-repo-name`).textContent = result.name;
                        document.getElementById(`${tab}-repo-owner`).textContent = `${result.owner} / ${result.name}`;
                        document.getElementById(`${tab}-stars`).textContent = formatNumber(result.stars);
                        document.getElementById(`${tab}-forks`).textContent = formatNumber(result.forks);
                        document.getElementById(`${tab}-issues`).textContent = formatNumber(result.issues);
                        
                        repoInfo.classList.add('show');
                        selectedBranches[tab] = result.default_branch;
                        if (parsed.isFullRepo) fetchBranches(tab, parsed, token);
                    } else {
                        showStatus(tab, 'warning', 'Public Repository', 'Switching To Public Tab...');
                        setTimeout(() => {
                            switchTab('public');
                            document.getElementById('public-url').value = document.getElementById('private-url').value;
                            handleUrlInput('public', document.getElementById('public-url').value);
                        }, 1000);
                    }
                } else {
                    if (tab === 'public') {
                        showStatus('public', 'warning', 'Private Repository', 'Switching To Private Tab...');
                        setTimeout(() => {
                            switchTab('private');
                            document.getElementById('private-url').value = document.getElementById('public-url').value;
                            handleUrlInput('private', document.getElementById('private-url').value);
                        }, 1000);
                    } else {
                        showStatus(tab, 'success', 'Access Confirmed', 'Access confirmed. Please click download.');
                    }
                }

            } catch (e) { console.error('Error fetching repo info:', e); }
        }

        async function fetchBranches(tab, parsed, token) {
            try {
                const branches = await pyCall('get_branches', `https://github.com/${parsed.owner}/${parsed.repo}`, token);
                if (!branches) return;
                const branchList = document.getElementById(`${tab}-branch-list`);
                const branchCount = document.getElementById(`${tab}-branch-count`);
                const branchSelector = document.getElementById(`${tab}-branch-selector`);
                branchCount.textContent = `${branches.length} branches`;
                branchList.innerHTML = branches.map(branch => `<div class="branch-item ${branch === selectedBranches[tab] ? 'active' : ''}" onclick="selectBranch('${tab}', '${branch}')">${branch}</div>`).join('');
                branchSelector.classList.add('show');
            } catch (e) { console.error('Error fetching branches:', e); }
        }

        function selectBranch(tab, branch) {
            selectedBranches[tab] = branch;
            document.querySelectorAll(`#${tab}-branch-list .branch-item`).forEach(item => item.classList.toggle('active', item.textContent.trim() === branch));
        }

        function formatNumber(num) { return num >= 1000 ? (num / 1000).toFixed(1) + 'k' : num.toString(); }
        function showStatus(tab, type, title, message) { const status = document.getElementById(`${tab}-status`); status.className = `status show ${type}`; status.querySelector('.status-title').textContent = title; status.querySelector('.status-message').textContent = message; }
        function hideStatus(tab) { document.getElementById(`${tab}-status`).classList.remove('show'); }
        
        function setButtonLoading(tab, loading) {
            const btn = document.getElementById(`${tab}-btn`);
            const btnText = btn.querySelector('span');
            const btnIcon = btn.querySelector('.btn-icon');
            
            clearInterval(loadingInterval);
            
            if (loading) {
                btn.disabled = true;
                btnIcon.style.display = 'none';
                
                const spinner = document.createElement('div');
                spinner.className = 'spinner';
                btn.insertBefore(spinner, btnText);
                
                let dots = 0;
                const baseText = 'Processing';
                loadingInterval = setInterval(() => {
                    dots = (dots + 1) % 4;
                    btnText.textContent = baseText + '.'.repeat(dots);
                }, 400);
                
            } else {
                btn.disabled = false;
                
                const spinner = btn.querySelector('.spinner');
                if (spinner) spinner.remove();
                
                btnIcon.style.display = 'block';
                btnText.textContent = 'Download';
            }
        }

        function updateProgress(tab, percent, text) { const progressContainer = document.getElementById(`${tab}-progress`); const progressFill = progressContainer.querySelector('.progress-fill'); const progressPercent = progressContainer.querySelector('.progress-percent'); const progressText = progressContainer.querySelector('.progress-text'); progressContainer.classList.add('show'); progressFill.style.width = `${percent}%`; progressPercent.textContent = `${Math.round(percent)}%`; if (text) progressText.textContent = text; }
        function hideProgress(tab) { document.getElementById(`${tab}-progress`).classList.remove('show'); }
        function renderFileTree(tab, files, repoName, dirPath) { const treeContainer = document.getElementById(`${tab}-tree`); const filesCount = files.filter(f => f.type === 'file').length; const foldersCount = files.filter(f => f.type === 'dir').length; let html = `<div class="file-tree-header"><span>${dirPath ? dirPath : repoName}</span><span class="file-count">${filesCount} files / ${foldersCount} folders</span></div>`; files.forEach(file => { const isFolder = file.type === 'dir'; const icon = isFolder ? `<svg class="file-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>` : `<svg class="file-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>`; html += `<div class="file-item ${isFolder ? 'folder' : ''}">${icon}<span>${file.name}</span></div>`; }); treeContainer.innerHTML = html; treeContainer.classList.add('show'); }
        
        async function handlePublicSubmit(event) { event.preventDefault(); await startDownload('public'); }
        async function handlePrivateSubmit(event) { event.preventDefault(); await startDownload('private'); }

        async function startDownload(tab) {
            const url = document.getElementById(`${tab}-url`).value.trim();
            let token = tab === 'private' ? document.getElementById('private-token').value.trim() : null;
            
            if (!url) { showStatus(tab, 'error', 'Input Required', 'Please enter a GitHub URL'); return; }
            
            const parsed = parseGitHubUrlLocal(url);
            if (!parsed) {
                showStatus(tab, 'error', 'Invalid Format', 'Please enter a valid GitHub repository link.');
                return; 
            }

            if (tab === 'private' && !token) {
                showStatus(tab, 'error', 'Access Denied', 'Please enter a valid Token for this repository.');
                return;
            }

            setButtonLoading(tab, true);
            hideStatus(tab);
            hideProgress(tab);
            document.getElementById(`${tab}-tree`).classList.remove('show');

            try {
                showStatus(tab, 'info', 'Verifying', 'Checking repository access...');
                
                const checkResult = await pyCall('check_repo', url, token);

                if (!checkResult.valid) {
                    if (checkResult.needs_token) {
                        if (tab === 'public') {
                           showStatus('public', 'warning', 'Private Repository', 'Switching To Private Tab...');
                           setTimeout(() => {
                                switchTab('private');
                                document.getElementById('private-url').value = url;
                           }, 1000); 
                        } else {
                           showStatus(tab, 'error', 'Access Denied', 'Please enter a valid Token for this repository.');
                        }
                    } else {
                        let title = "Connection Error";
                        if(checkResult.error && checkResult.error.includes('Rate Limit')) title = "Rate Limit Exceeded";
                        else if(checkResult.error && checkResult.error.includes('not found')) title = "Not Found";
                        showStatus(tab, 'error', title, checkResult.error || 'Access denied');
                    }
                    return;
                }

                if (tab === 'private' && checkResult.private === false) {
                    showStatus(tab, 'warning', 'Public Repository', 'Switching To Public Tab...');
                    setTimeout(() => {
                        switchTab('public');
                        document.getElementById('public-url').value = url;
                    }, 1000);
                    return;
                }

                showStatus(tab, 'success', 'Verified', 'Access confirmed. Please click download.');

                const savePath = await pyCall('select_folder');
                if (!savePath) {
                    return;
                }

                await pyCall('start_download', url, token, selectedBranches[tab], savePath);
                
            } catch (error) {
                showStatus(tab, 'error', 'Download Failed', error.message || 'An error occurred');
                hideProgress(tab);
            } finally {
                setButtonLoading(tab, false);
            }
        }

        document.addEventListener('keydown', (e) => { if (e.key === 'Tab' && e.altKey) { e.preventDefault(); switchTab(currentTab === 'public' ? 'private' : 'public'); } });
        document.querySelectorAll('.form-input').forEach(input => {
            input.addEventListener('focus', () => { const label = input.parentElement.querySelector('.form-label'); if (label) label.style.color = 'var(--accent)'; });
            input.addEventListener('blur', () => { const label = input.parentElement.querySelector('.form-label'); if (label) label.style.color = 'var(--muted)'; });
        });
    </script>
</body>
</html>
"""

def main():
    api = Api()
    window = webview.create_window('GitHub Downloader', html=HTML_TEMPLATE, js_api=api, width=900, height=750, resizable=True, frameless=False)
    api.window = window
    webview.start(debug=False)

if __name__ == '__main__':
    main()