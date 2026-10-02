"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

from archipelago.inference import state as st
import torch


@st.app.route("/")
def server_root():
    
    gpu_info = "N/A"
    if torch.cuda.is_available():
        try:
            gpu_info = f"Active ({torch.cuda.get_device_name(0)}, Memory: {torch.cuda.memory_allocated(0)/(1024**2):.1f}MB allocated)"
        except Exception as e:
            gpu_info = f"Available but inactive: {e}"
            
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Archipelago Inference Server Diagnostic</title>
        <meta charset="utf-8">
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
        <style>
            :root {{
                --bg: #0f0a15;
                --card-bg: rgba(255, 255, 255, 0.03);
                --bd: rgba(255, 255, 255, 0.08);
                --tx: #f3f0f7;
                --tx-mu: #a59fb1;
                --accent: #8b5cf6;
                --success: #10b981;
                --warning: #f59e0b;
            }}
            body {{
                background: var(--bg);
                color: var(--tx);
                font-family: 'Outfit', sans-serif;
                margin: 0;
                padding: 40px;
                display: flex;
                flex-direction: column;
                align-items: center;
                min-height: 100vh;
                box-sizing: border-box;
            }}
            .container {{
                max-width: 800px;
                width: 100%;
            }}
            h1 {{
                font-size: 32px;
                font-weight: 800;
                margin-bottom: 8px;
                background: linear-gradient(135deg, #a78bfa, #f472b6);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                letter-spacing: -0.5px;
            }}
            .subtitle {{
                color: var(--tx-mu);
                margin-bottom: 40px;
                font-size: 16px;
            }}
            .grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                gap: 20px;
                margin-bottom: 40px;
            }}
            .card {{
                background: var(--card-bg);
                border: 1px solid var(--bd);
                border-radius: 16px;
                padding: 24px;
                backdrop-filter: blur(20px);
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            }}
            .card-title {{
                font-size: 11px;
                font-weight: 600;
                color: var(--tx-mu);
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-bottom: 12px;
            }}
            .card-value {{
                font-size: 18px;
                font-weight: 600;
                display: flex;
                align-items: center;
                gap: 8px;
            }}
            .status-dot {{
                width: 10px;
                height: 10px;
                border-radius: 50%;
                display: inline-block;
            }}
            .status-dot.active {{
                background: var(--success);
                box-shadow: 0 0 10px var(--success);
            }}
            .status-dot.inactive {{
                background: var(--warning);
                box-shadow: 0 0 10px var(--warning);
            }}
            .explain-section {{
                background: rgba(139, 92, 246, 0.05);
                border: 1px solid rgba(139, 92, 246, 0.2);
                border-radius: 16px;
                padding: 24px;
                margin-bottom: 40px;
                line-height: 1.6;
            }}
            .explain-title {{
                font-weight: 600;
                margin-bottom: 8px;
                color: #c084fc;
            }}
            .test-form {{
                background: var(--card-bg);
                border: 1px solid var(--bd);
                border-radius: 16px;
                padding: 28px;
            }}
            input[type="text"] {{
                width: 100%;
                padding: 12px 16px;
                border-radius: 10px;
                border: 1px solid var(--bd);
                background: rgba(0,0,0,0.2);
                color: #fff;
                font-family: inherit;
                outline: none;
                margin-bottom: 16px;
                box-sizing: border-box;
            }}
            input[type="text"]:focus {{
                border-color: var(--accent);
            }}
            button {{
                background: var(--accent);
                color: #fff;
                border: none;
                padding: 12px 24px;
                border-radius: 10px;
                font-weight: 600;
                cursor: pointer;
                font-family: inherit;
                transition: opacity 0.15s;
            }}
            button:hover {{
                opacity: 0.9;
            }}
            pre {{
                background: rgba(0,0,0,0.4);
                padding: 16px;
                border-radius: 10px;
                overflow-x: auto;
                font-size: 12.5px;
                margin-top: 16px;
                border: 1px solid var(--bd);
                color: #86efac;
                white-space: pre-wrap;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Archipelago Inference Server</h1>
            <div class="subtitle">Diagnostic & Local RAG Control Panel (Port 5051)</div>
            
            <div class="grid">
                <div class="card">
                    <div class="card-title">Embedding Model</div>
                    <div class="card-value">
                        <span class="status-dot {'active' if st.use_embeddings else 'inactive'}"></span>
                        <span>{'Active (Snowflake)' if st.use_embeddings else 'Loading / Standby'}</span>
                    </div>
                </div>
                <div class="card">
                    <div class="card-title">Generator Model</div>
                    <div class="card-value">
                        <span class="status-dot active"></span>
                        <span>Ollama ({st.DEFAULT_OLLAMA_MODEL})</span>
                    </div>
                </div>
                <div class="card">
                    <div class="card-title">KuzuDB Status</div>
                    <div class="card-value">
                        <span class="status-dot active"></span>
                        <span>{len(st.CONCEPTS_DATA)} Concepts</span>
                    </div>
                </div>
            </div>
            
            <div class="explain-section">
                <div class="explain-title">💨 Why is my computer's fan spinning?</div>
                <div>
                    The local inference server runs two models directly on your hardware (GPU: {gpu_info}):
                    <ul>
                        <li><strong>Snowflake Arctic Embed (M)</strong>: Converts query text into a 768-dimensional dense vector to find concept anchors in KuzuDB.</li>
                        <li><strong>Ollama ({st.DEFAULT_OLLAMA_MODEL})</strong>: Natural language synthesis over retrieved graph notes — runs via local Ollama server.</li>
                        <li><strong>lib-qwen (1.5B SLM, extraction-only)</strong>: Used exclusively during ingestion to extract concepts from PDFs. Not loaded at inference time.</li>
                    </ul>
                    Because these models run locally, loading model weights into memory and compiling tensors creates a temporary CPU/GPU load, which spins the system fan to cool down the processor.
                </div>
            </div>
            
            <div class="test-form">
                <div class="card-title" style="margin-bottom:16px;">Test Inference Directly</div>
                <input type="text" id="query" placeholder="Enter a concept (e.g. What is LoRA?)..." value="What is LoRA?">
                <button onclick="runTest()">Run Inference</button>
                <div id="output-section" style="display:none;">
                    <div class="card-title" style="margin-top:20px; margin-bottom:8px;">Response Payload</div>
                    <pre id="output"></pre>
                </div>
            </div>
        </div>
        
        <script>
            function runTest() {{
                const query = document.getElementById('query').value;
                const output = document.getElementById('output');
                const outSec = document.getElementById('output-section');
                outSec.style.display = 'block';
                output.textContent = 'Initializing stream...';
                
                fetch('/api/chat', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ query: query, mode: 'rag_synthesis', history: [] }})
                }})
                .then(res => {{
                    if (!res.ok) throw new Error("HTTP error " + res.status);
                    const reader = res.body.getReader();
                    const decoder = new TextDecoder();
                    let buffer = '';
                    let metadataParsed = false;
                    output.textContent = '';
                    
                    function read() {{
                        return reader.read().then(({{ done, value }}) => {{
                            if (done) {{
                                if (buffer) {{
                                    output.textContent += buffer;
                                }}
                                return;
                            }}
                            buffer += decoder.decode(value, {{ stream: true }});
                            
                            if (!metadataParsed) {{
                                const index = buffer.indexOf('\n[STREAM_START]\n');
                                if (index !== -1) {{
                                    const metaStr = buffer.substring(0, index);
                                    buffer = buffer.substring(index + 16);
                                    metadataParsed = true;
                                    output.textContent += "--- RETRIEVAL METADATA ---\n" + 
                                        JSON.stringify(JSON.parse(metaStr), null, 2) + 
                                        "\n\n--- ARCHIPELAGO GENERATION ---\n";
                                }}
                            }}
                            
                            if (metadataParsed) {{
                                output.textContent += buffer;
                                buffer = '';
                            }}
                            
                            return read();
                        }});
                    }}
                    return read();
                }})
                .catch(err => {{
                    output.textContent = 'Error: ' + err;
                }});
            }}
        </script>
    </body>
    </html>
    """
    return html
