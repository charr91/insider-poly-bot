from flask import Flask, render_template_string, jsonify
import json
from datetime import datetime, timedelta

app = Flask(__name__)

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Insider Activity Monitor</title>
    <style>
        body { 
            background: #0a0a0a; 
            color: #0f0; 
            font-family: 'Courier New', monospace;
        }
        .alert-critical {
            background: #ff0000;
            color: white;
            padding: 10px;
            animation: blink 1s infinite;
        }
        @keyframes blink {
            50% { opacity: 0.5; }
        }
        .alert-high {
            background: #ff6600;
            color: white;
            padding: 10px;
        }
        .whale-indicator {
            font-size: 2em;
            color: #00ffff;
        }
        .market-card {
            border: 1px solid #0f0;
            padding: 10px;
            margin: 10px;
            background: #001100;
        }
    </style>
</head>
<body>
    <h1>🔍 INSIDER ACTIVITY MONITOR</h1>
    <div id="alerts"></div>
    <div id="markets"></div>
    
    <script>
        function refreshData() {
            fetch('/api/alerts')
                .then(r => r.json())
                .then(data => {
                    const alertsDiv = document.getElementById('alerts');
                    alertsDiv.innerHTML = data.alerts.map(alert => `
                        <div class="alert-${alert.severity.toLowerCase()}">
                            🚨 ${alert.severity}: ${alert.market}
                            <br>Volume: ${alert.volume_spike}x
                            <br>Price Move: ${alert.price_change}%
                            <br>Action: ${alert.action}
                        </div>
                    `).join('');
                });
        }
        
        setInterval(refreshData, 2000);
        refreshData();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/alerts')
def get_alerts():
    # Read from shared memory/redis/file
    return jsonify({
        'alerts': [],  # Would be populated from bot
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    app.run(port=5001, debug=True)