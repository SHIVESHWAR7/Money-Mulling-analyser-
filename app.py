import os
import time
import json
import pandas as pd
import networkx as nx
from flask import Flask, request, jsonify, send_file, render_template_string
from werkzeug.utils import secure_filename
from datetime import datetime
import uuid
from collections import defaultdict

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
os.makedirs('uploads', exist_ok=True)

analysis_results = {}

# ================= CONFIG =================
class Config:
    FAN_IN_THRESHOLD = 8
    MIN_CYCLE_LENGTH = 3
    MAX_CYCLE_LENGTH = 5
    MAX_CYCLE_NODES = 2000

config = Config()

# ================= PREMIUM UI =================
HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MuleSight | Fraud Intelligence</title>
    
    <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">

    <style>
        :root {
            --primary: #6366f1;
            --danger: #ef4444;
            --warning: #f59e0b;
            --success: #10b981;
            --bg-dark: #020617;
            --glass: rgba(15, 23, 42, 0.6);
            --border: rgba(255, 255, 255, 0.1);
        }

        * { box-sizing: border-box; }
        body {
            margin: 0;
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-dark);
            background-image: 
                radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.15) 0, transparent 50%),
                radial-gradient(at 100% 100%, rgba(239, 68, 68, 0.1) 0, transparent 50%);
            color: #f8fafc;
            min-height: 100vh;
            display: flex;
            overflow-x: hidden;
        }

        /* Sidebar Navigation */
        aside {
            width: 300px;
            background: var(--glass);
            backdrop-filter: blur(20px);
            border-right: 1px solid var(--border);
            padding: 30px;
            display: flex;
            flex-direction: column;
            gap: 20px;
            height: 100vh;
            position: fixed;
            z-index: 100;
        }

        .logo {
            font-size: 24px;
            font-weight: 800;
            background: linear-gradient(to right, #818cf8, #f472b6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 30px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        /* Main Content Area */
        main {
            margin-left: 300px;
            padding: 30px;
            width: calc(100% - 300px);
        }

        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }

        .glass-card {
            background: var(--glass);
            backdrop-filter: blur(15px);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 20px;
            transition: all 0.3s ease;
        }

        .glass-card:hover {
            border-color: var(--primary);
            box-shadow: 0 0 20px rgba(99, 102, 241, 0.2);
        }

        /* Metrics */
        .metric-val {
            font-size: 32px;
            font-weight: 700;
            margin: 10px 0 5px 0;
            display: block;
        }
        .metric-label {
            color: #94a3b8;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        /* Buttons & Inputs */
        .upload-zone {
            border: 2px dashed var(--border);
            padding: 20px;
            border-radius: 12px;
            text-align: center;
            cursor: pointer;
            margin-bottom: 10px;
        }
        .upload-zone:hover { border-color: var(--primary); }
        
        button {
            width: 100%;
            padding: 14px;
            border-radius: 12px;
            border: none;
            background: var(--primary);
            color: white;
            font-weight: 600;
            cursor: pointer;
            transition: 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }
        button:hover { filter: brightness(1.2); transform: translateY(-2px); }
        button.secondary { background: rgba(255,255,255,0.05); border: 1px solid var(--border); }

        /* Visualization Blocks */
        .viz-container {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 20px;
        }

        #network {
            height: 550px;
            background: rgba(0,0,0,0.2);
            border-radius: 12px;
        }

        /* Table Styling */
        .table-container {
            max-height: 400px;
            overflow-y: auto;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th {
            position: sticky; top: 0;
            background: #1e293b;
            text-align: left;
            padding: 12px;
            font-size: 12px;
            color: #94a3b8;
        }
        td {
            padding: 12px;
            border-bottom: 1px solid var(--border);
            font-size: 14px;
        }

        /* Status Animations */
        .pulse {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--success);
            box-shadow: 0 0 0 rgba(16, 185, 129, 0.4);
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
            70% { box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }
            100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
        }

        #loading {
            color: var(--primary);
            font-weight: 600;
            text-align: center;
            display: none;
        }

        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 10px; }
    </style>
</head>

<body>

<aside>
    <div class="logo">
        <i class="fas fa-shield-nodes"></i> MuleSight
    </div>
    
    <div class="upload-zone" onclick="document.getElementById('file').click()">
        <i class="fas fa-cloud-upload-alt" style="font-size: 24px; color: var(--primary)"></i>
        <p style="font-size: 13px; margin-top:10px">Drop transaction CSV here</p>
        <input type="file" id="file" hidden>
    </div>

    <button onclick="analyze()">
        <i class="fas fa-bolt"></i> Run Intelligence
    </button>
    
    <button class="secondary" onclick="downloadReport()">
        <i class="fas fa-file-export"></i> Export Intelligence
    </button>

    <div id="loading">
        <i class="fas fa-circle-notch fa-spin"></i> Analyzing Graph...
    </div>

    <div style="margin-top: auto; font-size: 11px; color: #475569; border-top: 1px solid var(--border); pt: 20px">
        v2.4 Engine Active <span class="pulse"></span>
    </div>
</aside>

<main>
    <div class="dashboard-grid">
        <div class="glass-card">
            <span class="metric-label">Nodes Monitored</span>
            <span class="metric-val" id="total">-</span>
        </div>
        <div class="glass-card">
            <span class="metric-label">High Risk Flagged</span>
            <span class="metric-val" style="color: var(--danger)" id="suspicious">-</span>
        </div>
        <div class="glass-card">
            <span class="metric-label">Circular Chains</span>
            <span class="metric-val" style="color: var(--warning)" id="rings">-</span>
        </div>
        <div class="glass-card">
            <span class="metric-label">Latency</span>
            <span class="metric-val" id="time">-</span>
        </div>
    </div>

    <div class="glass-card" style="margin-bottom: 30px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
            <h3 style="margin:0">Network Topology</h3>
            <span style="font-size:12px; color: #94a3b8">Interactive Graph Visualizer</span>
        </div>
        <div id="network"></div>
    </div>

    <div class="viz-container">
        <div class="glass-card">
            <h3>Risk Registry</h3>
            <div class="table-container">
                <table id="accountsTable">
                    <thead>
                        <tr><th>ENTITY ID</th><th>RISK SCORE</th><th>STATUS</th></tr>
                    </thead>
                    <tbody>
                        </tbody>
                </table>
            </div>
        </div>

        <div class="glass-card">
            <h3>Risk Distribution</h3>
            <div style="padding: 20px;">
                <canvas id="riskChart"></canvas>
            </div>
        </div>
    </div>
</main>

<script>
    let currentId = null;
    let chart = null;

    async function analyze() {
        const file = document.getElementById("file").files[0];
        if(!file) { alert("Please select a transaction file."); return; }

        document.getElementById("loading").style.display = "block";

        const formData = new FormData();
        formData.append("file", file);

        try {
            const res = await fetch("/analyze", { method: "POST", body: formData });
            const data = await res.json();
            
            document.getElementById("loading").style.display = "none";
            currentId = data.result_id;

            animateValue("total", data.summary.total_accounts_analyzed);
            animateValue("suspicious", data.summary.suspicious_accounts_flagged);
            animateValue("rings", data.summary.fraud_rings_detected);
            document.getElementById("time").innerText = data.summary.processing_time_seconds + "s";

            const options = {
                physics: { 
                    stabilization: { iterations: 150 },
                    barnesHut: { gravitationalConstant: -10000 }
                },
                nodes: {
                    shape: 'dot',
                    font: { color: '#ffffff', size: 12 },
                    borderWidth: 2
                },
                edges: {
                    color: { inherit: 'from' },
                    arrows: "to",
                    smooth: { type: 'continuous' }
                }
            };

            new vis.Network(document.getElementById("network"), data.graph_data, options);
            populateTable(data.suspicious_accounts);
            buildChart(data.suspicious_accounts);
        } catch (e) {
            alert("Analysis failed. Check console for details.");
            document.getElementById("loading").style.display = "none";
        }
    }

    function animateValue(id, end) {
        let start = 0;
        const duration = 1000;
        const step = Math.max(1, end / (duration / 16));
        const el = document.getElementById(id);
        const interval = setInterval(() => {
            start += step;
            if(start >= end) {
                el.innerText = end.toLocaleString();
                clearInterval(interval);
            } else {
                el.innerText = Math.floor(start).toLocaleString();
            }
        }, 16);
    }

    function populateTable(accounts) {
        const tbody = document.querySelector("#accountsTable tbody");
        tbody.innerHTML = "";
        accounts.sort((a,b) => b.score - a.score).forEach(acc => {
            const status = acc.score > 70 ? 'CRITICAL' : 'ELEVATED';
            const color = acc.score > 70 ? 'var(--danger)' : 'var(--warning)';
            tbody.innerHTML += `
                <tr>
                    <td style="font-family: monospace">${acc.account_id}</td>
                    <td style="font-weight:bold; color:${color}">${acc.score}%</td>
                    <td><span style="background:${color}33; color:${color}; padding:4px 8px; border-radius:4px; font-size:10px">${status}</span></td>
                </tr>`;
        });
    }

    function buildChart(accounts) {
        let high = 0, mid = 0, low = 0;
        accounts.forEach(acc => {
            if(acc.score > 70) high++;
            else if(acc.score > 40) mid++;
            else low++;
        });

        if(chart) chart.destroy();
        chart = new Chart(document.getElementById("riskChart"), {
            type: "doughnut",
            data: {
                labels: ["High Risk", "Medium Risk", "Low Risk"],
                datasets: [{
                    data: [high, mid, low],
                    backgroundColor: ["#ef4444", "#f59e0b", "#10b981"],
                    borderWidth: 0,
                    hoverOffset: 10
                }]
            },
            options: {
                plugins: { legend: { position: 'bottom', labels: { color: '#94a3b8' } } },
                cutout: '70%'
            }
        });
    }

    function downloadReport() {
        if(!currentId) { alert("Generate an analysis first."); return; }
        window.location = "/download/" + currentId;
    }
</script>

</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

# ================= CORE ANALYSIS =================
def parse_csv(path):
    df=pd.read_csv(path)
    required=['transaction_id','sender_id','receiver_id','amount','timestamp']
    if not all(col in df.columns for col in required):
        raise ValueError("CSV missing required columns")

    df['amount']=pd.to_numeric(df['amount'],errors='coerce')
    df['timestamp']=pd.to_datetime(df['timestamp'],errors='coerce')
    df=df.dropna()
    df=df[df['amount']>0]
    return df

@app.route('/analyze',methods=['POST'])
def analyze():
    start=time.time()
    file=request.files['file']
    filename=secure_filename(str(uuid.uuid4())+"_"+file.filename)
    path=os.path.join(app.config['UPLOAD_FOLDER'],filename)
    file.save(path)

    df=parse_csv(path)
    G=nx.DiGraph()

    for row in df.itertuples(index=False):
        G.add_edge(row.sender_id,row.receiver_id)

    cycles=[]
    if len(G.nodes())<config.MAX_CYCLE_NODES:
        try:
            for c in nx.simple_cycles(G):
                if config.MIN_CYCLE_LENGTH<=len(c)<=config.MAX_CYCLE_LENGTH:
                    cycles.append(c)
        except:
            pass

    fan_in=df.groupby('receiver_id')['sender_id'].nunique()
    smurf=fan_in[fan_in>=config.FAN_IN_THRESHOLD]

    scores=defaultdict(float)
    for c in cycles:
        for acc in c: scores[acc]+=40
    for acc in smurf.index:
        scores[acc]+=30

    if scores:
        m=max(scores.values())
        for k in scores: scores[k]=round((scores[k]/m)*100,2)

    suspicious=[{"account_id":k,"score":v} for k,v in scores.items() if v>50]

    nodes=[]
    for n in G.nodes():
        s=scores.get(n,0)
        color="#00e676"
        if s>70: color="#ff1744"
        elif s>40: color="#ff9100"
        nodes.append({"id":n,"label":n[:6],"value":s+10,"color":color})

    edges=[{"from":u,"to":v} for u,v in G.edges()]

    result_id=str(uuid.uuid4())

    output={
        "result_id":result_id,
        "summary":{
            "total_accounts_analyzed":len(G.nodes()),
            "suspicious_accounts_flagged":len(suspicious),
            "fraud_rings_detected":len(cycles),
            "processing_time_seconds":round(time.time()-start,2)
        },
        "suspicious_accounts":suspicious,
        "graph_data":{"nodes":nodes,"edges":edges}
    }

    analysis_results[result_id]=output
    os.remove(path)

    return jsonify(output)

@app.route('/download/<rid>')
def download(rid):
    if rid not in analysis_results:
        return jsonify({"error":"Not found"}),404
    filename=f"mulesight_{datetime.now().strftime('%H%M%S')}.json"
    path=os.path.join(app.config['UPLOAD_FOLDER'],filename)
    with open(path,"w") as f:
        json.dump(analysis_results[rid],f,indent=2)
    return send_file(path,as_attachment=True)

if __name__=="__main__":
    print("🚀 MuleSight Premium Running")
    app.run(debug=True)
