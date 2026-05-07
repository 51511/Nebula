"""
Blogroll 關係圖視覺化（互動版）
用法：
    pip install pyvis
    python visualize_graph.py
    用瀏覽器開啟 blogroll_graph.html
"""

import json
from pyvis.network import Network

with open("blogroll_graph.json", encoding="utf-8") as f:
    g = json.load(f)

in_degree = {}
for v in g.values():
    for d in v["links_to"]:
        in_degree[d] = in_degree.get(d, 0) + 1

net = Network(height="100vh", width="100%", bgcolor="#1a1a2e", font_color="white", directed=True)
net.barnes_hut(gravity=-3000, central_gravity=0.3, spring_length=120)

for domain, info in g.items():
    size = 8 + in_degree.get(domain, 0) * 2.5
    size = min(size, 60)
    color = "#7F77DD" if info["blogroll_url"] else "#5F5E5A"
    title = f"{domain}\n連出: {len(info['links_to'])}  被連: {in_degree.get(domain, 0)}"
    net.add_node(domain, label=domain if in_degree.get(domain, 0) >= 3 else "",
                 size=size, color=color, title=title)

for domain, info in g.items():
    for target in info["links_to"]:
        if target in g:
            net.add_edge(domain, target, color="rgba(255,255,255,0.08)", arrows="to")

net.save_graph("blogroll_graph.html")

# 注入自訂 UI
with open("blogroll_graph.html", encoding="utf-8") as f:
    html = f.read()

custom_css = """
<style>
* { box-sizing: border-box; }
body { margin: 0; font-family: system-ui, sans-serif; background: #1a1a2e; color: #eee; }
#mynetwork { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 0; }

#panel {
  position: fixed; top: 12px; left: 12px; z-index: 10;
  background: rgba(20,20,40,0.92);
  border: 1px solid rgba(255,255,255,0.15);
  border-radius: 12px;
  padding: 12px 14px;
  width: 280px;
  backdrop-filter: blur(8px);
}
#panel h3 { margin: 0 0 10px; font-size: 14px; color: #aaa; font-weight: 500; }

#search-row { display: flex; gap: 6px; margin-bottom: 8px; }
#search { flex: 1; padding: 6px 10px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.2);
  background: rgba(255,255,255,0.08); color: #fff; font-size: 13px; }
#search::placeholder { color: #666; }
#search-btn { padding: 6px 10px; border-radius: 8px; border: none;
  background: #534AB7; color: #fff; cursor: pointer; font-size: 13px; }
#search-btn:hover { background: #6a60d0; }

#results { max-height: 140px; overflow-y: auto; margin-bottom: 8px; }
.result-item {
  padding: 5px 8px; border-radius: 6px; cursor: pointer;
  font-size: 12px; display: flex; justify-content: space-between; align-items: center;
}
.result-item:hover { background: rgba(255,255,255,0.1); }
.result-item .badge { font-size: 10px; color: #aaa; }

#info-box {
  border-top: 1px solid rgba(255,255,255,0.1);
  padding-top: 10px;
  display: none;
}
#info-domain {
  font-size: 13px; font-weight: 600; color: #c0bbff;
  word-break: break-all; margin-bottom: 6px;
  cursor: pointer; display: flex; align-items: center; gap: 6px;
}
#info-domain:hover { color: #fff; }
#copy-hint { font-size: 10px; color: #666; }
#info-stats { font-size: 12px; color: #aaa; margin-bottom: 8px; }
#neighbors-title { font-size: 11px; color: #888; margin-bottom: 4px; }
#neighbors { max-height: 160px; overflow-y: auto; }
.neighbor-item {
  font-size: 11px; padding: 3px 6px; border-radius: 4px;
  cursor: pointer; display: flex; justify-content: space-between;
}
.neighbor-item:hover { background: rgba(255,255,255,0.08); }
.neighbor-item .dir { font-size: 10px; color: #7F77DD; }

#legend {
  position: fixed; bottom: 12px; left: 12px; z-index: 10;
  background: rgba(20,20,40,0.85);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 10px; padding: 8px 12px;
  font-size: 11px; color: #aaa;
  display: flex; gap: 14px;
}
.legend-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; margin-right: 4px; }

#toast {
  position: fixed; bottom: 60px; left: 50%; transform: translateX(-50%);
  background: #534AB7; color: #fff; padding: 6px 16px; border-radius: 20px;
  font-size: 13px; z-index: 100; opacity: 0; transition: opacity 0.3s;
  pointer-events: none;
}
</style>
"""

custom_html = """
<div id="panel">
  <h3>🔍 Blogroll 關係圖</h3>
  <div id="search-row">
    <input id="search" placeholder="搜尋域名..." autocomplete="off" />
    <button id="search-btn">搜尋</button>
  </div>
  <div id="results"></div>
  <div id="info-box">
    <div id="info-domain">
      <span id="info-domain-text"></span>
      <span id="copy-hint">點擊複製</span>
    </div>
    <div id="info-stats"></div>
    <div id="neighbors-title"></div>
    <div id="neighbors"></div>
  </div>
</div>

<div id="legend">
  <span><span class="legend-dot" style="background:#7F77DD"></span>有 Blogroll</span>
  <span><span class="legend-dot" style="background:#5F5E5A"></span>葉節點</span>
  <span>節點大小 = 被連次數</span>
</div>

<div id="toast">已複製！</div>

<script>
const graphData = """ + json.dumps({
    k: {
        "blogroll_url": v["blogroll_url"],
        "links_to": v["links_to"],
        "in_degree": in_degree.get(k, 0)
    }
    for k, v in g.items()
}) + """;

function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.opacity = '1';
  setTimeout(() => t.style.opacity = '0', 1500);
}

function copyDomain(domain) {
  navigator.clipboard.writeText(domain).then(() => showToast('已複製：' + domain));
}

function focusNode(domain) {
  if (!window.network) return;
  const nodeId = domain;
  network.focus(nodeId, { scale: 1.5, animation: true });
  network.selectNodes([nodeId]);
  showNodeInfo(domain);
}

function showNodeInfo(domain) {
  const data = graphData[domain];
  if (!data) return;

  document.getElementById('info-box').style.display = 'block';
  document.getElementById('info-domain-text').textContent = domain;
  document.getElementById('info-domain').onclick = () => copyDomain(domain);

  const outLen = data.links_to.length;
  const inLen = data.in_degree;
  const hasBlog = data.blogroll_url ? '✓ 有 Blogroll' : '✗ 無 Blogroll';
  document.getElementById('info-stats').innerHTML =
    `${hasBlog} &nbsp;|&nbsp; 連出 ${outLen} &nbsp;|&nbsp; 被連 ${inLen}`;

  // 找誰連到這個節點
  const inNodes = [];
  for (const [k, v] of Object.entries(graphData)) {
    if (v.links_to.includes(domain) && k !== domain) inNodes.push(k);
  }

  document.getElementById('neighbors-title').textContent =
    `連結關係（連出 ${outLen}，被連 ${inNodes.length}）`;

  const nb = document.getElementById('neighbors');
  nb.innerHTML = '';

  for (const t of data.links_to) {
    const el = document.createElement('div');
    el.className = 'neighbor-item';
    el.innerHTML = `<span>${t}</span><span class="dir">→ 連出</span>`;
    el.onclick = () => focusNode(t);
    nb.appendChild(el);
  }
  for (const s of inNodes) {
    const el = document.createElement('div');
    el.className = 'neighbor-item';
    el.innerHTML = `<span>${s}</span><span class="dir">← 被連</span>`;
    el.onclick = () => focusNode(s);
    nb.appendChild(el);
  }
}

// 搜尋
function doSearch() {
  const q = document.getElementById('search').value.trim().toLowerCase();
  const res = document.getElementById('results');
  res.innerHTML = '';
  if (!q) return;
  const matches = Object.keys(graphData).filter(d => d.includes(q)).slice(0, 20);
  for (const d of matches) {
    const data = graphData[d];
    const el = document.createElement('div');
    el.className = 'result-item';
    el.innerHTML = `<span>${d}</span><span class="badge">被連${data.in_degree}</span>`;
    el.onclick = () => { focusNode(d); res.innerHTML = ''; document.getElementById('search').value = d; };
    res.appendChild(el);
  }
  if (!matches.length) res.innerHTML = '<div style="font-size:12px;color:#666;padding:4px 8px;">找不到</div>';
}

document.getElementById('search-btn').onclick = doSearch;
document.getElementById('search').addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });

// 等 vis network 載入後掛上點擊事件
function waitForNetwork() {
  if (window.network) {
    network.on('click', function(params) {
      if (params.nodes.length > 0) {
        showNodeInfo(params.nodes[0]);
      }
    });
    network.on('doubleClick', function(params) {
      if (params.nodes.length > 0) {
        copyDomain(params.nodes[0]);
      }
    });
  } else {
    setTimeout(waitForNetwork, 300);
  }
}
waitForNetwork();
</script>
"""

# 插入到 </body> 前
html = html.replace("</head>", custom_css + "</head>")
html = html.replace("</body>", custom_html + "</body>")

with open("blogroll_graph.html", "w", encoding="utf-8") as f:
    f.write(html)

print("完成！用瀏覽器開啟 blogroll_graph.html")
