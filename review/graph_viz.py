"""知识图谱可视化：用 ECharts 渲染（内联本地 JS，离线可用，无第三方组件依赖）。

节点颜色 = 掌握度（由 records.mastery_color 提供）；被问次数显示在 tooltip。
"""
import json
from pathlib import Path

import records

# 节点大小（按类型）
TYPE_SIZE = {"core": 34, "hub": 24, "leaf": 16}

_LOCAL_JS = Path(__file__).resolve().parent / "static" / "echarts.min.js"


def build_option(nodes, children, mastery_map, highlight_ids=None):
    """构造 ECharts graph 选项（树层级边 + 跨树 wiki 边）。"""
    highlight = set(highlight_ids or [])
    data = []
    edges = []
    seen = set()

    for nid, n in nodes.items():
        entry = mastery_map.get(nid)
        color = records.mastery_color(entry)
        cnt = entry["count"] if entry else 0
        is_hl = nid in highlight
        data.append(
            {
                "id": nid,
                "name": n.title,
                "value": cnt,
                "summary": n.summary,
                "type": n.type,
                "symbolSize": (TYPE_SIZE.get(n.type, 18) + 10) if is_hl else TYPE_SIZE.get(n.type, 18),
                "itemStyle": {
                    "color": color,
                    "borderColor": "#2b6cb0" if is_hl else "#e2e8f0",
                    "borderWidth": 3 if is_hl else 1,
                },
            }
        )
        # 树层级边
        if n.parent and n.parent in nodes:
            k = ("h", n.parent, nid)
            if k not in seen:
                edges.append({"source": n.parent, "target": nid, "lineStyle": {"color": "#cbd5e0", "width": 1}})
                seen.add(k)
        # 跨树 wiki 边（虚线）
        for lk in n.links:
            tgt = lk.get("id")
            if tgt in nodes:
                k = ("w", nid, tgt)
                if k not in seen:
                    edges.append(
                        {
                            "source": nid,
                            "target": tgt,
                            "lineStyle": {"color": "#e2c67a", "width": 0.5, "type": "dashed", "opacity": 0.5},
                        }
                    )
                    seen.add(k)

    return {
        "backgroundColor": "#ffffff",
        "animationDuration": 400,
        "series": [
            {
                "type": "graph",
                "layout": "force",
                "roam": True,
                "draggable": True,
                "data": data,
                "edges": edges,
                "label": {"show": True, "position": "right", "fontSize": 9, "color": "#4a5568"},
                "force": {"repulsion": 430, "edgeLength": [40, 120], "gravity": 0.06},
                "emphasis": {"focus": "adjacency", "lineStyle": {"width": 3}},
            }
        ],
    }


_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0">
<div id="chart" style="width:100%;height:__HEIGHT__px;"></div>
__ECHARTS_SCRIPT__
<script>
// esc：tooltip 里动态文本（节点名/摘要来自知识库，可能含 HTML）先转义再进 innerHTML，防注入
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
var option = __OPTION__;
function init(){
  var chart = echarts.init(document.getElementById('chart'));
  option.tooltip = {
    trigger: 'item',
    formatter: function(p){
      var d = p.data;
      var t = d.type==='core' ? '核心节点' : (d.type==='hub' ? '枢纽节点' : '叶子节点');
      var html = '<b>'+esc(d.name)+'</b> <span style="color:#999">['+esc(d.id)+']</span><br/>'
               + '被问次数：'+(d.value||0)+' · '+t;
      if(d.summary){ html += '<br/><span style="color:#888">'+esc(d.summary)+'</span>'; }
      return html;
    }
  };
  chart.setOption(option);
  window.addEventListener('resize', function(){ chart.resize(); });
}
init();
</script>
</body></html>"""


def graph_html(option, height=620):
    """把 ECharts 选项渲染成可嵌入的自包含 HTML 字符串。

    - 只内联本地 static/echarts.min.js（随仓库分发），不加载任何第三方 CDN；
    - option JSON 用 ensure_ascii=True 并把 `</` 转义为 `<\\/`：节点 title/summary
      来自知识库（开源可被贡献），直接内联进 <script> 会形成闭合逃逸（存储型 XSS）。
    """
    if not _LOCAL_JS.exists():
        raise FileNotFoundError(f"缺少本地 ECharts 库：{_LOCAL_JS}（已随仓库分发，请勿删除）")
    opt_json = json.dumps(option, ensure_ascii=True).replace("</", "<\\/")

    html = _TEMPLATE
    html = html.replace("__HEIGHT__", str(height))
    html = html.replace("__ECHARTS_SCRIPT__", "<script>" + _LOCAL_JS.read_text(encoding="utf-8") + "</script>")
    html = html.replace("__OPTION__", opt_json)
    return html
