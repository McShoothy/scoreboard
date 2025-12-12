"""
Utility functions for the RobotUprising Tournament app
"""
import re
import html
from markupsafe import Markup, escape


def sanitize_text(text, max_length=100):
    """
    Sanitize text input to prevent XSS attacks.
    - Escapes HTML entities
    - Removes potentially dangerous characters
    - Limits length
    """
    if text is None:
        return ""
    
    # Convert to string
    text = str(text)
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    # Limit length
    if max_length:
        text = text[:max_length]
    
    # Remove null bytes and other control characters (except newline/tab)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    
    # HTML escape to prevent XSS
    text = html.escape(text, quote=True)
    
    return text


def sanitize_team_name(name):
    """Sanitize team name - alphanumeric, spaces, and common punctuation only. Max 8 chars."""
    if name is None:
        return ""
    
    name = str(name).strip()[:8]  # Max 8 characters for team names
    
    # Allow only safe characters for team names
    # Alphanumeric, spaces, hyphens, underscores, dots, apostrophes
    name = re.sub(r'[^\w\s\-_.\'&!]', '', name, flags=re.UNICODE)
    
    # Remove multiple consecutive spaces
    name = re.sub(r'\s+', ' ', name)
    
    # HTML escape
    name = html.escape(name, quote=True)
    
    return name


def sanitize_player_name(name):
    """Sanitize player name - more permissive than team names. Max 10 chars."""
    if name is None:
        return ""
    
    name = str(name).strip()[:10]  # Max 10 characters for player names
    
    # Allow alphanumeric, spaces, hyphens, underscores, dots
    name = re.sub(r'[^\w\s\-_.]', '', name, flags=re.UNICODE)
    
    # Remove multiple consecutive spaces
    name = re.sub(r'\s+', ' ', name)
    
    # HTML escape
    name = html.escape(name, quote=True)
    
    return name


def sanitize_message(message):
    """Sanitize custom message for display"""
    if message is None:
        return ""
    
    message = str(message).strip()[:500]
    
    # Remove potentially dangerous tags but keep basic formatting intent
    # HTML escape everything
    message = html.escape(message, quote=True)
    
    return message


# Theme definitions - Complete visual overhauls
THEMES = {
    'dark-orange': {
        'name': 'Robot Orange',
        'type': 'dark',
        'description': 'The classic RobotUprising theme',
        'primary': '#ff6b00',
        'secondary': '#252538',
        'dark': '#1c1c2a',
        'darker': '#14141f',
        'light': '#f5f5f5',
        'text': '#e8e8e8',
        'muted': '#9a9ab0',
        'border': '#3a3a50',
        'success': '#28a745',
        'danger': '#dc3545',
        'bg_gradient': 'linear-gradient(135deg, #14141f 0%, #1c1c2a 50%, #252538 100%)',
        'bg_pattern': 'linear-gradient(rgba(255, 107, 0, 0.08) 1px, transparent 1px), linear-gradient(90deg, rgba(255, 107, 0, 0.08) 1px, transparent 1px)',
        'bg_pattern_size': '40px 40px',
        'glow_color': 'rgba(255, 107, 0, 0.3)',
        'card_glow': '0 0 20px rgba(255, 107, 0, 0.1)',
    },
    'hacker': {
        'name': 'Ultra Hacker',
        'type': 'dark',
        'description': 'Matrix-style terminal aesthetic',
        'primary': '#00ff41',
        'secondary': '#0a0a0a',
        'dark': '#050505',
        'darker': '#000000',
        'light': '#00ff41',
        'text': '#00dd35',
        'muted': '#006b1a',
        'border': '#003d0f',
        'success': '#00ff41',
        'danger': '#ff0040',
        'bg_gradient': 'linear-gradient(180deg, #000000 0%, #001a00 100%)',
        'bg_pattern': '''
            repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0, 255, 65, 0.03) 2px, rgba(0, 255, 65, 0.03) 4px),
            repeating-linear-gradient(90deg, transparent, transparent 50px, rgba(0, 255, 65, 0.02) 50px, rgba(0, 255, 65, 0.02) 51px)
        ''',
        'bg_pattern_size': '100% 100%',
        'glow_color': 'rgba(0, 255, 65, 0.5)',
        'card_glow': '0 0 30px rgba(0, 255, 65, 0.15), inset 0 0 20px rgba(0, 255, 65, 0.05)',
        'font_family': "'Courier New', 'Fira Code', monospace",
        'scanline': True,
    },
    'princess': {
        'name': 'Pink Princess',
        'type': 'light',
        'description': 'Sparkly pink fantasy theme',
        'primary': '#ff69b4',
        'secondary': '#fff0f5',
        'dark': '#ffe4ec',
        'darker': '#fff5f8',
        'light': '#4a1a2c',
        'text': '#5c2a3e',
        'muted': '#c97a9a',
        'border': '#ffb6c8',
        'success': '#50c878',
        'danger': '#ff4466',
        'bg_gradient': 'linear-gradient(135deg, #fff5f8 0%, #ffe4ec 25%, #ffd6e7 50%, #ffe4ec 75%, #fff5f8 100%)',
        'bg_pattern': '''
            radial-gradient(circle at 20% 80%, rgba(255, 105, 180, 0.15) 0%, transparent 50%),
            radial-gradient(circle at 80% 20%, rgba(255, 182, 193, 0.2) 0%, transparent 50%),
            radial-gradient(circle at 40% 40%, rgba(255, 20, 147, 0.08) 0%, transparent 30%)
        ''',
        'bg_pattern_size': '100% 100%',
        'glow_color': 'rgba(255, 105, 180, 0.4)',
        'card_glow': '0 4px 20px rgba(255, 105, 180, 0.15)',
        'sparkle': True,
    },
    'midnight': {
        'name': 'Midnight Blue',
        'type': 'dark',
        'description': 'Professional dark blue theme',
        'primary': '#4a90d9',
        'secondary': '#1a2332',
        'dark': '#141c28',
        'darker': '#0d1320',
        'light': '#e8f0f8',
        'text': '#c8d4e0',
        'muted': '#6b7c8f',
        'border': '#2a3a4f',
        'success': '#32cd70',
        'danger': '#e74c3c',
        'bg_gradient': 'linear-gradient(160deg, #0d1320 0%, #1a2332 50%, #1e2d42 100%)',
        'bg_pattern': '''
            radial-gradient(ellipse at top, rgba(74, 144, 217, 0.1) 0%, transparent 50%),
            linear-gradient(rgba(74, 144, 217, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(74, 144, 217, 0.03) 1px, transparent 1px)
        ''',
        'bg_pattern_size': '100% 100%, 60px 60px, 60px 60px',
        'glow_color': 'rgba(74, 144, 217, 0.3)',
        'card_glow': '0 2px 15px rgba(74, 144, 217, 0.1)',
    },
    'sunset': {
        'name': 'Warm Sunset',
        'type': 'dark',
        'description': 'Warm orange and purple gradient',
        'primary': '#ff7b54',
        'secondary': '#2d1f3d',
        'dark': '#1f1528',
        'darker': '#150e1a',
        'light': '#ffe8db',
        'text': '#e8d5d0',
        'muted': '#9a7a8a',
        'border': '#4a3555',
        'success': '#4ade80',
        'danger': '#f87171',
        'bg_gradient': 'linear-gradient(135deg, #150e1a 0%, #2d1f3d 40%, #3d2a4a 70%, #4a2c4a 100%)',
        'bg_pattern': '''
            radial-gradient(ellipse at bottom right, rgba(255, 123, 84, 0.15) 0%, transparent 50%),
            radial-gradient(ellipse at top left, rgba(138, 43, 226, 0.1) 0%, transparent 50%)
        ''',
        'bg_pattern_size': '100% 100%',
        'glow_color': 'rgba(255, 123, 84, 0.35)',
        'card_glow': '0 4px 25px rgba(255, 123, 84, 0.1)',
    },
    'minimal': {
        'name': 'Clean Minimal',
        'type': 'light',
        'description': 'Simple, clean white theme',
        'primary': '#2563eb',
        'secondary': '#ffffff',
        'dark': '#f3f4f6',
        'darker': '#ffffff',
        'light': '#111827',
        'text': '#374151',
        'muted': '#6b7280',
        'border': '#e5e7eb',
        'success': '#10b981',
        'danger': '#ef4444',
        'bg_gradient': 'linear-gradient(180deg, #ffffff 0%, #f9fafb 100%)',
        'bg_pattern': 'none',
        'bg_pattern_size': '100% 100%',
        'glow_color': 'rgba(37, 99, 235, 0.2)',
        'card_glow': '0 1px 3px rgba(0, 0, 0, 0.1)',
    },
}


def get_theme(theme_id):
    """Get theme by ID, defaults to dark-orange"""
    return THEMES.get(theme_id, THEMES['dark-orange'])


def get_all_themes():
    """Get all available themes"""
    return THEMES


def generate_theme_css(theme_id):
    """Generate CSS custom properties for a theme"""
    theme = get_theme(theme_id)
    
    css = f"""
    :root {{
        --ru-primary: {theme['primary']};
        --ru-secondary: {theme['secondary']};
        --ru-dark: {theme['dark']};
        --ru-darker: {theme['darker']};
        --ru-light: {theme['light']};
        --ru-text: {theme['text']};
        --ru-muted: {theme['muted']};
        --ru-border: {theme['border']};
        --ru-success: {theme['success']};
        --ru-danger: {theme['danger']};
        --theme-type: {theme['type']};
        --glow-color: {theme.get('glow_color', 'rgba(255,255,255,0.2)')};
    }}
    
    body {{
        background: {theme.get('bg_gradient', theme['darker'])};
        background-attachment: fixed;
    }}
    
    body::before {{
        content: '';
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-image: {theme.get('bg_pattern', 'none')};
        background-size: {theme.get('bg_pattern_size', '100% 100%')};
        pointer-events: none;
        z-index: -1;
    }}
    
    .card {{
        box-shadow: {theme.get('card_glow', 'none')} !important;
    }}
    
    .btn-ru:hover {{
        box-shadow: 0 0 15px var(--glow-color);
    }}
    """
    
    # Hacker theme special effects
    if theme.get('scanline'):
        css += """
    body::after {
        content: '';
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: repeating-linear-gradient(
            0deg,
            transparent,
            transparent 2px,
            rgba(0, 0, 0, 0.1) 2px,
            rgba(0, 0, 0, 0.1) 4px
        );
        pointer-events: none;
        z-index: 9999;
        animation: scanlines 0.1s linear infinite;
    }
    
    @keyframes scanlines {
        0% { transform: translateY(0); }
        100% { transform: translateY(4px); }
    }
    
    body {
        font-family: 'Courier New', 'Fira Code', monospace !important;
    }
    
    h1, h2, h3, h4, h5, h6, .card, .btn, input, select {
        font-family: 'Courier New', 'Fira Code', monospace !important;
    }
    
    .card {
        border: 1px solid var(--ru-primary) !important;
        background: rgba(0, 10, 0, 0.95) !important;
    }
    
    .card::before {
        content: '> ';
        position: absolute;
        top: 10px;
        left: 10px;
        color: var(--ru-primary);
        animation: blink 1s infinite;
    }
    
    @keyframes blink {
        0%, 100% { opacity: 1; }
        50% { opacity: 0; }
    }
    
    input, select, .form-control {
        border: 1px solid var(--ru-primary) !important;
        background: #000 !important;
        color: var(--ru-primary) !important;
    }
    
    .btn-ru {
        text-transform: uppercase;
        letter-spacing: 2px;
    }
    """
    
    # Princess theme special effects  
    if theme.get('sparkle'):
        css += """
    body::after {
        content: '✨ ⭐ 💖 ✨ ⭐ 💖 ✨ ⭐ 💖 ✨';
        position: fixed;
        top: 0;
        left: 0;
        width: 200%;
        height: 100%;
        font-size: 2rem;
        opacity: 0.15;
        pointer-events: none;
        z-index: -1;
        animation: sparkle-float 20s linear infinite;
        white-space: nowrap;
        word-spacing: 100px;
        line-height: 150px;
    }
    
    @keyframes sparkle-float {
        0% { transform: translate(0, 0); }
        100% { transform: translate(-50%, 0); }
    }
    
    .card {
        border-radius: 20px !important;
        border: 2px solid var(--ru-primary) !important;
    }
    
    .btn-ru {
        border-radius: 25px !important;
        font-weight: 700;
    }
    
    h1, h2, h3 {
        color: var(--ru-primary) !important;
    }
    """
    
    # Light theme specific overrides
    if theme['type'] == 'light':
        css += """
    .navbar {
        background-color: var(--ru-secondary) !important;
        border-bottom: 1px solid var(--ru-border);
    }
    
    .navbar-brand, .nav-link {
        color: var(--ru-text) !important;
    }
    
    .nav-link:hover {
        color: var(--ru-primary) !important;
    }
    
    .table {
        color: var(--ru-text);
    }
    
    .btn-outline-secondary {
        color: var(--ru-text);
        border-color: var(--ru-border);
    }
    
    .dropdown-menu {
        background-color: var(--ru-secondary);
        border: 1px solid var(--ru-border);
    }
    
    .dropdown-item {
        color: var(--ru-text);
    }
    
    .dropdown-item:hover {
        background-color: var(--ru-dark);
    }
    
    .form-control, .form-select {
        background-color: var(--ru-secondary);
        border-color: var(--ru-border);
        color: var(--ru-text);
    }
    """
    
    return css
