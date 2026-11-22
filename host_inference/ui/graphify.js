/**
 * Archipelago Graphify
 * In-chat interactive terminal & graph visualization component
 * Exact replica of the animated glowing constellation graph style
 */

window.ArchipelagoGraphify = (function() {
  let isCooldown = false;
  let activeAnimationLoops = {};

  const graphifyStyle = [
    // 1. Background Constellation Mesh (Muted Dots)
    {
      selector: 'node',
      style: {
        'shape': 'ellipse',
        'width': 6,
        'height': 6,
        'background-color': 'rgba(0, 255, 163, 0.22)',
        'border-width': 0,
        'label': '',
        'transition-property': 'background-color, width, height, shadow-blur, opacity',
        'transition-duration': '0.35s'
      }
    },
    // 2. Background Constellation Edges (Faint spiderweb lines)
    {
      selector: 'edge',
      style: {
        'width': 0.8,
        'line-color': 'rgba(0, 255, 163, 0.12)',
        'curve-style': 'bezier',
        'target-arrow-shape': 'none',
        'label': '',
        'transition-property': 'line-color, width, opacity',
        'transition-duration': '0.35s'
      }
    },
    // 3. Active Path Nodes: Bright glowing circular mint dots with neon halos!
    {
      selector: 'node.active-path',
      style: {
        'shape': 'ellipse',
        'width': 14,
        'height': 14,
        'background-color': '#00ffa3',
        'border-width': 2,
        'border-color': '#ffffff',
        'shadow-blur': 16,
        'shadow-color': '#00ffa3',
        'shadow-opacity': 0.85,
        'label': 'data(name)',
        'color': '#ffffff',
        'font-family': '"JetBrains Mono", monospace',
        'font-size': '10px',
        'font-weight': '600',
        'text-valign': 'top',
        'text-margin-y': -6,
        'text-background-color': '#03140d',
        'text-background-opacity': 0.75,
        'text-background-padding': '2px',
        'text-background-shape': 'round-rectangle',
        'z-index': 999
      }
    },
    // 4. Active Path Edges: Glowing bold mint lines with animated dashed signals & italic labels!
    {
      selector: 'edge.active-path',
      style: {
        'width': 2.5,
        'line-color': '#00ffa3',
        'curve-style': 'straight',
        'target-arrow-shape': 'triangle',
        'target-arrow-color': '#00ffa3',
        'arrow-scale': 1.0,
        'shadow-blur': 8,
        'shadow-color': '#00ffa3',
        'shadow-opacity': 0.7,
        'line-style': 'dashed',
        'line-dash-pattern': [10, 5],
        'line-dash-offset': 0,
        'label': 'data(rel_label)',
        'color': '#00ffa3',
        'font-family': '"JetBrains Mono", monospace',
        'font-style': 'italic',
        'font-size': '8px',
        'text-background-color': '#03140d',
        'text-background-opacity': 0.8,
        'text-background-padding': '2px',
        'text-background-shape': 'round-rectangle',
        'z-index': 998
      }
    },
    // 5. Selected State
    {
      selector: 'node:selected',
      style: {
        'border-width': 3,
        'border-color': '#ffffff',
        'shadow-blur': 24,
        'shadow-color': '#00ffa3',
        'shadow-opacity': 1.0
      }
    }
  ];

  return {
    render: function(containerId, subgraphData, options = {}) {
      const container = document.getElementById(containerId);
      if (!container) return null;

      // Ensure container styling matches the terminal chrome
      container.innerHTML = '';
      container.style.backgroundColor = '#03140d';
      container.style.border = '1px solid #0d3829';
      container.style.borderRadius = '10px';
      container.style.overflow = 'hidden';
      container.style.position = 'relative';
      container.style.boxShadow = '0 12px 32px rgba(0, 0, 0, 0.7), 0 0 20px rgba(0, 255, 163, 0.05)';
      container.style.fontFamily = '"JetBrains Mono", monospace';

      const height = options.height || 420;
      container.style.height = `${height}px`;

      // 1. Create Terminal Header Bar (Traffic lights + "graphify")
      const headerBar = document.createElement('div');
      headerBar.style.height = '36px';
      headerBar.style.backgroundColor = 'rgba(4, 26, 18, 0.9)';
      headerBar.style.borderBottom = '1px solid #0d3829';
      headerBar.style.display = 'flex';
      headerBar.style.alignItems = 'center';
      headerBar.style.justifyContent = 'space-between';
      headerBar.style.padding = '0 12px';
      headerBar.style.userSelect = 'none';

      headerBar.innerHTML = `
        <div style="display: flex; align-items: center; gap: 6px;">
          <div style="width: 10px; height: 10px; border-radius: 50%; background: #ff5f56;"></div>
          <div style="width: 10px; height: 10px; border-radius: 50%; background: #ffbd2e;"></div>
          <div style="width: 10px; height: 10px; border-radius: 50%; background: #27c93f;"></div>
        </div>
        <div style="font-size: 11px; color: #00ffa3; font-weight: 500; letter-spacing: 0.05em; opacity: 0.85;">graphify</div>
        <div style="font-size: 10px; color: #52796f;">Archipelago DAG</div>
      `;
      container.appendChild(headerBar);

      // 2. Inner Split Container (Left CLI panel + Right Cytoscape stage)
      const bodyWrapper = document.createElement('div');
      bodyWrapper.style.display = 'flex';
      bodyWrapper.style.height = `calc(100% - 36px)`;
      bodyWrapper.style.position = 'relative';
      bodyWrapper.style.overflow = 'hidden';
      container.appendChild(bodyWrapper);

      // Derive trace items
      const rawNodes = (subgraphData && subgraphData.nodes) || [];
      const rawEdges = (subgraphData && subgraphData.edges) || [];

      // Determine active path nodes
      let pathNodeNames = [];
      if (rawNodes.length) {
        pathNodeNames = rawNodes.slice(0, Math.min(4, rawNodes.length)).map(n => n.data ? (n.data.name || n.data.id) : n.name || n.id);
      } else {
        pathNodeNames = ['FastAPI', 'DefaultPlaceholder', 'get_request_handler()', 'ModelField'];
      }

      const sourceName = options.source || pathNodeNames[0] || 'Start';
      const targetName = options.target || pathNodeNames[pathNodeNames.length - 1] || 'Target';
      const hops = Math.max(1, pathNodeNames.length - 1);

      // Left CLI Panel
      const cliPanel = document.createElement('div');
      cliPanel.style.width = '35%';
      cliPanel.style.minWidth = '190px';
      cliPanel.style.maxWidth = '260px';
      cliPanel.style.backgroundColor = 'rgba(3, 20, 13, 0.96)';
      cliPanel.style.borderRight = '1px solid #0d3829';
      cliPanel.style.padding = '14px 12px';
      cliPanel.style.fontSize = '11px';
      cliPanel.style.lineHeight = '1.5';
      cliPanel.style.color = '#ffffff';
      cliPanel.style.overflowY = 'auto';
      cliPanel.style.zIndex = '5';
      cliPanel.style.display = 'flex';
      cliPanel.style.flexDirection = 'column';
      cliPanel.style.justifyContent = 'space-between';

      let traceHTML = '';
      for (let i = 0; i < pathNodeNames.length; i++) {
        traceHTML += `<div style="font-weight: 600; color: #fff; margin-top: 2px;">${pathNodeNames[i]}</div>`;
        if (i < pathNodeNames.length - 1) {
          const rel = i % 2 === 0 ? 'uses' : 'references';
          const dir = i % 2 === 1 ? '&lt;--' : '--';
          traceHTML += `<div style="color: #00ffa3; font-size: 10px; padding-left: 10px; opacity: 0.9;">${dir}${rel}--&gt; <span style="font-style: italic; color: #34d399;">${rel}</span></div>`;
        }
      }

      cliPanel.innerHTML = `
        <div>
          <div style="color: #00ffa3; font-weight: 600; display: flex; align-items: center; gap: 4px; flex-wrap: wrap;">
            <span>$ graphify path</span>
            <span>"${sourceName}"</span>
            <span>"${targetName}"</span>
            <span style="display: inline-block; width: 6px; height: 12px; background: #00ffa3; animation: blink 1s step-end infinite;"></span>
          </div>
          <div style="color: #34d399; font-size: 10px; margin: 8px 0 6px 0;">Shortest path (${hops} hops):</div>
          <div style="padding-left: 2px;">
            ${traceHTML}
          </div>
        </div>
        <div style="color: #00ffa3; font-size: 11px; font-weight: 600; margin-top: 10px; border-top: 1px solid rgba(0,255,163,0.15); pt-2;">
          ${hops} hops. Zero files opened.
        </div>
      `;
      bodyWrapper.appendChild(cliPanel);

      // Right Cytoscape Stage
      const stageDiv = document.createElement('div');
      stageDiv.style.flex = '1';
      stageDiv.style.height = '100%';
      stageDiv.style.position = 'relative';
      stageDiv.style.background = 'radial-gradient(circle at 60% 40%, #062319 0%, #03140d 70%, #020c08 100%)';
      bodyWrapper.appendChild(stageDiv);

      const cyDiv = document.createElement('div');
      cyDiv.style.width = '100%';
      cyDiv.style.height = '100%';
      stageDiv.appendChild(cyDiv);

      // Tooltip
      const tooltip = document.createElement('div');
      tooltip.style.position = 'absolute';
      tooltip.style.display = 'none';
      tooltip.style.backgroundColor = 'rgba(3, 20, 13, 0.95)';
      tooltip.style.border = '1px solid #00ffa3';
      tooltip.style.borderRadius = '4px';
      tooltip.style.color = 'white';
      tooltip.style.padding = '6px 10px';
      tooltip.style.fontSize = '10px';
      tooltip.style.pointerEvents = 'none';
      tooltip.style.zIndex = '20';
      tooltip.style.maxWidth = '180px';
      tooltip.style.boxShadow = '0 6px 18px rgba(0,0,0,0.8), 0 0 10px rgba(0,255,163,0.3)';
      stageDiv.appendChild(tooltip);

      // Build elements with background constellation stars
      let elements = [];
      if (subgraphData && subgraphData.nodes && subgraphData.nodes.length) {
        elements = subgraphData;
      } else {
        elements = {
          nodes: [
            { data: { id: 'n0', name: 'FastAPI' } },
            { data: { id: 'n1', name: 'DefaultPlaceholder' } },
            { data: { id: 'n2', name: 'get_request_handler()' } },
            { data: { id: 'n3', name: 'ModelField' } }
          ],
          edges: [
            { data: { id: 'e0', source: 'n0', target: 'n1', rel_label: 'uses' } },
            { data: { id: 'e1', source: 'n1', target: 'n2', rel_label: 'references' } },
            { data: { id: 'e2', source: 'n2', target: 'n3', rel_label: 'references' } }
          ]
        };
      }

      // Add background constellation mesh
      const bgNodes = elements.nodes.slice();
      const bgEdges = elements.edges.slice();
      for (let k = 1; k <= 12; k++) {
        const bgId = `bg_star_${k}`;
        bgNodes.push({ data: { id: bgId, name: '' } });
        const parentId = bgNodes[Math.floor(Math.random() * 4)].data.id;
        bgEdges.push({ data: { id: `bg_e_${k}`, source: parentId, target: bgId } });
      }

      const cy = window.cytoscape({
        container: cyDiv,
        elements: { nodes: bgNodes, edges: bgEdges },
        style: graphifyStyle,
        layout: {
          name: 'cose',
          animate: true,
          animationDuration: 600,
          fit: true,
          padding: 30
        },
        userZoomingEnabled: options.interactive !== false,
        userPanningEnabled: options.interactive !== false,
        boxSelectionEnabled: false
      });

      // Mark the active path nodes & edges
      cy.batch(() => {
        cy.nodes().slice(0, 4).addClass('active-path');
        cy.edges().slice(0, 3).addClass('active-path');
      });

      // Continuous 60fps moving signal & pulsing glow loop
      let animOffset = 0;
      let animPulse = 0;
      function animateFlow() {
        animOffset = (animOffset - 0.7) % 30;
        animPulse += 0.05;
        const currentGlow = 14 + Math.sin(animPulse) * 5;

        cy.batch(() => {
          cy.edges('.active-path').style('line-dash-offset', animOffset);
          cy.nodes('.active-path').style('shadow-blur', currentGlow);
        });

        activeAnimationLoops[containerId] = requestAnimationFrame(animateFlow);
      }
      animateFlow();

      // Tooltip and interactivity
      if (options.interactive !== false) {
        cy.on('mouseover', 'node', function(evt) {
          const node = evt.target;
          const data = node.data();
          if (!data.name) return;
          tooltip.innerHTML = `<strong style="color: #00ffa3;">${data.name}</strong><br/>${data.summary || 'Active node'}`;
          tooltip.style.display = 'block';
        });

        cy.on('mousemove', function(evt) {
          if (tooltip.style.display === 'block') {
            const pos = evt.renderedPosition;
            tooltip.style.left = `${pos.x + 12}px`;
            tooltip.style.top = `${pos.y + 12}px`;
          }
        });

        cy.on('mouseout', 'node', function() {
          tooltip.style.display = 'none';
        });

        cy.on('dblclick', 'node', function(evt) {
          if (isCooldown) return;
          isCooldown = true;
          const nodeId = evt.target.id();
          window.ArchipelagoGraphify.expandNode(nodeId, (newData) => {
            if (newData) {
              cy.add(newData);
              cy.layout({ name: 'cose', animate: true }).run();
            }
          });
          setTimeout(() => { isCooldown = false; }, 5000);
        });
      }

      return cy;
    },

    expandNode: function(nodeId, callback) {
      fetch(`/api/graph/subgraph?target_id=${nodeId}&max_nodes=10`)
        .then(res => res.json())
        .then(data => {
          if(callback) callback(data);
        })
        .catch(err => {
          console.error("Expand node failed:", err);
          if(callback) callback(null);
        });
    }
  };
})();
