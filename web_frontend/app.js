import {
  appendLocalChatEntry,
  buildChatRenderEntries,
  createChatFeedState,
  noteAuthoritativeChat,
} from './chat_state.js';

const state = {
  config: null,
  socket: null,
  joined: null,
  view: null,
  prompt: null,
  inspection: null,
  pathPreview: null,
  pendingAction: null,
  previewMode: 'walk',
  chatFeed: createChatFeedState(),
  autoConnect: false,
  selectedCharacterCardActorId: null,
  mapPan: {
    active: false,
    moved: false,
    startX: 0,
    startY: 0,
    scrollLeft: 0,
    scrollTop: 0,
  },
};

const els = {
  statusLine: document.querySelector('#status-line'),
  runtimeMode: document.querySelector('#runtime-mode'),
  controllerRole: document.querySelector('#controller-role'),
  sceneLabel: document.querySelector('#scene-label'),
  wsUrl: document.querySelector('#ws-url'),
  sessionId: document.querySelector('#session-id'),
  controllerId: document.querySelector('#controller-id'),
  controllerToken: document.querySelector('#controller-token'),
  connectButton: document.querySelector('#connect-button'),
  disconnectButton: document.querySelector('#disconnect-button'),
  portalLinks: document.querySelector('#portal-links'),
  mapLegend: document.querySelector('#map-legend'),
  mapToolbar: document.querySelector('#map-toolbar'),
  mapContainer: document.querySelector('#map-container'),
  inspectionPanel: document.querySelector('#inspection-panel'),
  chatLog: document.querySelector('#chat-log'),
  commandInput: document.querySelector('#command-input'),
  sendCommandButton: document.querySelector('#send-command-button'),
  resolveCheckButton: document.querySelector('#resolve-check-button'),
  characterCardSelect: document.querySelector('#character-card-select'),
  characterCardPanel: document.querySelector('#character-card-panel'),
  actionPanel: document.querySelector('#action-panel'),
  promptPanel: document.querySelector('#prompt-panel'),
  summaryPanel: document.querySelector('#summary-panel'),
};

function create(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function appendLocalEntry(entry) {
  appendLocalChatEntry(state.chatFeed, {
    entry_id: entry.entry_id,
    speaker: entry.speaker || 'System',
    text: entry.text,
    category: entry.category || 'system',
    visibility: entry.visibility || 'public',
  });
  renderChat();
}

function appendSystemEntry(category, text, speaker = 'System') {
  appendLocalEntry({
    speaker: category === 'error' ? 'Error' : speaker,
    text,
    category,
    visibility: 'public',
  });
}

function defaultTokenForController(controllerId) {
  return `${controllerId}-token`;
}

function readPortalPreset() {
  const params = new URLSearchParams(window.location.search);
  const controllerId = params.get('portal') || params.get('controller');
  if (!controllerId) return null;
  return {
    controllerId,
    controllerToken: params.get('token') || defaultTokenForController(controllerId),
    autoConnect: params.get('autoconnect') !== '0',
  };
}

async function loadConfig() {
  const response = await fetch('/config.json');
  state.config = await response.json();
  els.wsUrl.value = state.config.wsUrl;
  els.sessionId.value = state.config.sessionId;
  els.controllerId.innerHTML = '';
  for (const controller of state.config.availableControllers) {
    const option = document.createElement('option');
    option.value = controller.controllerId;
    option.textContent = `${controller.label} (${controller.role})`;
    els.controllerId.appendChild(option);
  }
  const saved = JSON.parse(localStorage.getItem('dnd-web-join') || 'null');
  if (saved) {
    els.wsUrl.value = saved.wsUrl || els.wsUrl.value;
    els.sessionId.value = saved.sessionId || els.sessionId.value;
    if (saved.controllerId) els.controllerId.value = saved.controllerId;
    if (saved.controllerToken) els.controllerToken.value = saved.controllerToken;
  } else {
    els.controllerToken.value = defaultTokenForController(els.controllerId.value);
  }
  const portalPreset = readPortalPreset();
  if (portalPreset && state.config.availableControllers.some(controller => controller.controllerId === portalPreset.controllerId)) {
    els.controllerId.value = portalPreset.controllerId;
    els.controllerToken.value = portalPreset.controllerToken;
    state.autoConnect = portalPreset.autoConnect;
  }
  renderPortalLinks();
}

function renderPortalLinks() {
  if (!els.portalLinks) return;
  els.portalLinks.innerHTML = '';
  const portals = state.config?.portalPages || [];
  if (!portals.length) {
    els.portalLinks.textContent = 'No quick portals available.';
    return;
  }
  for (const portal of portals) {
    const link = create('a', 'portal-link inline-pill', `${portal.label} portal`);
    link.href = portal.path;
    link.title = `Open ${portal.label} in a dedicated browser portal.`;
    els.portalLinks.appendChild(link);
  }
}

function persistJoinForm() {
  localStorage.setItem('dnd-web-join', JSON.stringify({
    wsUrl: els.wsUrl.value,
    sessionId: els.sessionId.value,
    controllerId: els.controllerId.value,
    controllerToken: els.controllerToken.value,
  }));
}

function disconnect() {
  if (state.socket) {
    state.socket.close();
    state.socket = null;
  }
  state.joined = null;
  state.view = null;
  state.prompt = null;
  state.inspection = null;
  state.pathPreview = null;
  state.pendingAction = null;
  state.chatFeed = createChatFeedState();
  state.selectedCharacterCardActorId = null;
  updateStatus('Disconnected');
  renderAll();
}

function connect() {
  disconnect();
  persistJoinForm();
  const socket = new WebSocket(els.wsUrl.value);
  state.socket = socket;
  updateStatus('Connecting...');
  socket.addEventListener('open', () => {
    socket.send(JSON.stringify({
      type: 'join',
      session_id: els.sessionId.value,
      controller_id: els.controllerId.value,
      controller_token: els.controllerToken.value,
    }));
  });
  socket.addEventListener('message', event => handleMessage(JSON.parse(event.data)));
  socket.addEventListener('close', () => {
    if (state.socket === socket) {
      state.socket = null;
      updateStatus('Disconnected');
    }
  });
  socket.addEventListener('error', () => appendSystemEntry('error', 'WebSocket transport error.'));
}

function handleMessage(message) {
  switch (message.type) {
    case 'joined':
      state.joined = message;
      updateStatus(`Connected as ${message.label}`);
      break;
    case 'view':
      state.view = message.view;
      noteAuthoritativeChat(state.chatFeed, message.view.chat_entries || []);
      state.prompt = message.view.prompt;
      if (!message.view.map && !message.view.travel) {
        state.inspection = null;
        state.pathPreview = null;
      } else if (message.view.travel && state.pathPreview?.actor_id) {
        state.pathPreview = null;
      } else if (message.view.map && state.pathPreview?.destination?.q !== undefined) {
        state.pathPreview = null;
      }
      if (!message.view.action_groups?.length) {
        state.pendingAction = null;
      }
      renderAll();
      break;
    case 'prompt':
      state.prompt = message.prompt;
      renderPrompt();
      break;
    case 'inspection':
      state.inspection = message.inspection;
      renderInspection();
      renderMap();
      break;
    case 'path_preview':
      state.pathPreview = message.preview;
      renderInspection();
      renderMap();
      break;
    case 'echo':
      appendLocalEntry(message.entry || {});
      break;
    case 'info':
      appendSystemEntry('system', message.message);
      break;
    case 'thinking':
      appendSystemEntry('thinking', message.message);
      break;
    case 'error':
      appendSystemEntry('error', message.message);
      break;
    default:
      appendSystemEntry('system', `Unhandled message: ${JSON.stringify(message)}`);
      break;
  }
}

function updateStatus(text) {
  els.statusLine.textContent = text;
}

function sendJson(payload) {
  if (!state.socket || state.socket.readyState !== WebSocket.OPEN) {
    appendSystemEntry('error', 'Not connected.');
    return;
  }
  state.socket.send(JSON.stringify(payload));
}

function sendCommand(text) {
  if (!text.trim()) return;
  sendJson({ type: 'command', text: text.trim() });
  els.commandInput.value = '';
}

function renderAll() {
  renderHeader();
  renderLegend();
  renderMapToolbar();
  renderMap();
  renderInspection();
  renderChat();
  renderCharacterCard();
  renderActions();
  renderPrompt();
  renderSummary();
}

function renderHeader() {
  const view = state.view;
  els.runtimeMode.textContent = `mode: ${view?.runtime_mode || '--'}`;
  els.controllerRole.textContent = `role: ${view?.role || state.joined?.role || '--'}`;
  const scene = view?.current_scene_id || view?.current_location_id || (view?.runtime_mode === 'character-creation' ? 'character-creation' : '--');
  els.sceneLabel.textContent = `scene: ${scene}`;
}

function renderLegend() {
  els.mapLegend.innerHTML = '';
  const view = state.view;
  const items = (view?.travel && !view?.map)
    ? [
        ['travel-terrain-road', 'Road or trail'],
        ['travel-terrain-forest', 'Forest or hills'],
        ['travel-route', 'Planned route'],
        ['travel-current', 'Party position'],
        ['travel-unknown', 'Undiscovered'],
      ]
    : [
        ['terrain-road', 'Road'],
        ['terrain-woods', 'Woods'],
        ['blocked', 'Blocked'],
        ['difficult', 'Difficult'],
        ['active', 'Active token'],
      ];
  for (const [css, label] of items) {
    const item = create('div');
    const swatch = create('span', 'swatch');
    swatch.classList.add(css);
    item.append(swatch, document.createTextNode(label));
    els.mapLegend.appendChild(item);
  }
}

function renderMapToolbar() {
  if (!els.mapToolbar) return;
  els.mapToolbar.innerHTML = '';
  const view = state.view;
  if (!view) return;
  if (view.map?.grid) {
    for (const mode of [
      ['walk', 'Walk'],
      ['elevation', 'Slope'],
      ['climb', 'Climb'],
      ['fly', 'Fly'],
    ]) {
      const [modeId, label] = mode;
      const button = create('button', state.previewMode === modeId ? null : 'secondary', label);
      button.type = 'button';
      button.addEventListener('click', () => {
        state.previewMode = modeId;
        appendSystemEntry('system', `Preview mode set to ${state.previewMode}.`);
      });
      els.mapToolbar.appendChild(button);
    }
    return;
  }
  if (!view.travel) return;
  for (const pace of [
    ['cautious', 'Cautious'],
    ['normal', 'Normal'],
    ['fast', 'Fast'],
  ]) {
    const [paceId, label] = pace;
    const button = create('button', view.travel.pace === paceId ? null : 'secondary', label);
    button.type = 'button';
    button.addEventListener('click', () => sendJson({ type: 'travel_set_pace', pace: paceId }));
    els.mapToolbar.appendChild(button);
  }
  const advance = create('button', 'secondary', 'Advance 1');
  advance.type = 'button';
  advance.disabled = !view.travel.planned_route || view.travel.status === 'interrupted';
  advance.addEventListener('click', () => sendJson({ type: 'travel_advance', steps: 1 }));
  els.mapToolbar.appendChild(advance);
  const resume = create('button', 'secondary', 'Resume');
  resume.type = 'button';
  resume.disabled = view.travel.status !== 'interrupted';
  resume.addEventListener('click', () => sendJson({ type: 'travel_resume' }));
  els.mapToolbar.appendChild(resume);
  if (view.role === 'dm' && view.travel.pending_hook) {
    const engage = create('button', null, 'Engage Hook');
    engage.type = 'button';
    engage.addEventListener('click', () => sendJson({ type: 'travel_engage' }));
    els.mapToolbar.appendChild(engage);
  }
}

function renderMap() {
  const view = state.view;
  els.mapContainer.innerHTML = '';
  const hasBattlefield = Boolean(view?.map?.grid);
  const hasTravel = Boolean(view?.travel);
  els.mapContainer.classList.toggle('map-empty', !hasBattlefield && !hasTravel);
  if (hasBattlefield) {
    renderBattlefieldMap(view.map);
    return;
  }
  if (hasTravel) {
    renderTravelMap(view.travel);
    return;
  }
  els.mapContainer.textContent = view?.runtime_mode === 'character-creation'
    ? 'Character creation is active. The campaign map will appear automatically when travel begins.'
    : 'No semantic map is active for this scene.';
}

function renderBattlefieldMap(map) {
  const grid = create('div', 'map-grid');
  grid.style.gridTemplateColumns = `repeat(${map.grid.width}, 42px)`;
  const tokenMap = new Map();
  const featureMap = new Map();
  for (const token of map.tokens || []) {
    const key = `${token.position.x},${token.position.y}`;
    if (!tokenMap.has(key)) tokenMap.set(key, []);
    tokenMap.get(key).push(token);
  }
  for (const feature of map.features || []) {
    for (const cell of feature.cells || []) {
      const key = `${cell.x},${cell.y}`;
      if (!featureMap.has(key)) featureMap.set(key, []);
      featureMap.get(key).push(feature);
    }
  }
  const previewPath = new Set((state.pathPreview?.path || []).map(point => `${point.x},${point.y},${point.z}`));
  const selectedKey = state.inspection?.position ? `${state.inspection.position.x},${state.inspection.position.y},${state.inspection.position.z}` : null;
  for (const cell of map.cells) {
    const tile = create('button', 'map-cell');
    tile.type = 'button';
    tile.classList.add(`terrain-${String(cell.terrain_id || 'open_ground').replace(/[^a-z0-9_-]/gi, '_')}`);
    tile.classList.add(`lighting-${String(cell.lighting || 'bright').replace(/[^a-z0-9_-]/gi, '_')}`);
    tile.classList.add(`obscurement-${String(cell.obscurement || 'none').replace(/[^a-z0-9_-]/gi, '_')}`);
    if (!cell.traversable || !cell.occupiable) tile.classList.add('blocked');
    if (cell.apparent_blocked) tile.classList.add('apparent-blocked');
    if (cell.difficult_terrain) tile.classList.add('difficult');
    if (selectedKey === `${cell.position.x},${cell.position.y},${cell.position.z}`) tile.classList.add('selected');
    if (previewPath.has(`${cell.position.x},${cell.position.y},${cell.position.z}`)) tile.classList.add('preview');
    tile.appendChild(create('div', 'cell-coord', `${cell.position.x},${cell.position.y}`));
    tile.appendChild(create('div', 'cell-elevation', `${cell.elevation_ft}ft`));
    tile.title = `(${cell.position.x},${cell.position.y},${cell.position.z}) | ${cell.terrain_id} | light ${cell.lighting} | obscurement ${cell.obscurement}`;
    const featureStack = create('div', 'feature-stack');
    for (const feature of featureMap.get(`${cell.position.x},${cell.position.y}`) || []) {
      const pill = create('div', 'feature-badge', String(feature.display_name || feature.feature_id).slice(0, 18));
      pill.title = feature.display_description || feature.display_name || feature.feature_id;
      featureStack.appendChild(pill);
    }
    tile.appendChild(featureStack);
    const stack = create('div', 'token-stack');
    for (const token of tokenMap.get(`${cell.position.x},${cell.position.y}`) || []) {
      const badgeText = token.visibility_state === 'visible'
        ? (token.name.replace(/[^0-9A-Z]/gi, '').slice(0, 2) || token.name.slice(0, 2))
        : '?';
      const badge = create('button', `token-badge ${token.side}`, badgeText);
      badge.type = 'button';
      badge.classList.add(`visibility-${token.visibility_state || 'visible'}`);
      if (token.is_active) badge.classList.add('active');
      badge.title = `${token.name} @ (${token.position.x},${token.position.y},${token.position.z})`;
      badge.addEventListener('click', event => {
        event.stopPropagation();
        if (state.pendingAction && state.pendingAction.target_kind === 'creature') {
          sendActionProposal({ group_id: state.pendingAction.group_id, option_id: state.pendingAction.option_id, target_actor_id: token.actor_id });
          return;
        }
        sendJson({ type: 'inspect_cell', x: token.position.x, y: token.position.y, z: token.position.z });
      });
      stack.appendChild(badge);
    }
    tile.appendChild(stack);
    tile.addEventListener('mousedown', event => {
      if (event.button === 2) event.preventDefault();
    });
    tile.addEventListener('click', () => {
      if (state.pendingAction && ['point', 'area'].includes(state.pendingAction.target_kind)) {
        sendActionProposal({ group_id: state.pendingAction.group_id, option_id: state.pendingAction.option_id, x: cell.position.x, y: cell.position.y, z: cell.position.z });
        return;
      }
      sendJson({ type: 'inspect_cell', x: cell.position.x, y: cell.position.y, z: cell.position.z });
      if (canPreviewMove()) {
        sendJson({ type: 'preview_move', x: cell.position.x, y: cell.position.y, z: cell.position.z, mode: state.previewMode });
      }
    });
    grid.appendChild(tile);
  }
  els.mapContainer.appendChild(grid);
}

function renderTravelMap(travel) {
  const layout = computeTravelLayout(travel.hexes || []);
  const shell = create('div', 'travel-hexmap');
  shell.style.width = `${layout.width}px`;
  shell.style.height = `${layout.height}px`;
  const landmarkNames = new Map((travel.landmarks || []).map(landmark => [landmark.landmark_id, landmark.name]));
  const selectedKey = state.inspection?.coord ? `${state.inspection.coord.q},${state.inspection.coord.r}` : null;
  const routeKeys = new Set((travel.planned_route?.path || []).map(coord => `${coord.q},${coord.r}`));
  for (const hex of travel.hexes || []) {
    const point = travelHexPixel(hex.coord, layout.minX, layout.minY);
    const node = create('button', 'travel-hex');
    node.type = 'button';
    node.style.left = `${point.left}px`;
    node.style.top = `${point.top}px`;
    node.classList.add(`travel-terrain-${String(hex.terrain_id || 'wilds').replace(/[^a-z0-9_-]/gi, '_')}`);
    if (!hex.discovered) node.classList.add('travel-unknown');
    if (!hex.traversable) node.classList.add('travel-blocked');
    if (hex.current_party) node.classList.add('travel-current');
    if (routeKeys.has(`${hex.coord.q},${hex.coord.r}`)) node.classList.add('travel-route');
    if (selectedKey === `${hex.coord.q},${hex.coord.r}`) node.classList.add('selected');
    node.appendChild(create('div', 'travel-coord', `${hex.coord.q},${hex.coord.r}`));
    const label = (hex.landmark_ids || []).map(id => landmarkNames.get(id) || id)[0] || hex.route_kind || hex.location_id || hex.terrain_id;
    node.appendChild(create('div', 'travel-label', String(label).slice(0, 22)));
    node.appendChild(create('div', 'travel-cost', `${hex.travel_cost_units}`));
    const titleBits = [
      `Hex ${hex.coord.q},${hex.coord.r}`,
      hex.terrain_id,
      `cost ${hex.travel_cost_units}`,
    ];
    if (hex.location_id) titleBits.push(hex.location_id);
    if ((hex.landmark_ids || []).length) titleBits.push((hex.landmark_ids || []).map(id => landmarkNames.get(id) || id).join(', '));
    node.title = titleBits.join(' | ');
    node.addEventListener('mousedown', event => {
      if (event.button === 2) event.preventDefault();
    });
    node.addEventListener('click', () => {
      sendJson({ type: 'inspect_travel_hex', q: hex.coord.q, r: hex.coord.r });
      if (!(hex.current_party && !travel.planned_route)) {
        sendJson({ type: 'travel_route_preview', q: hex.coord.q, r: hex.coord.r });
      }
    });
    shell.appendChild(node);
  }
  els.mapContainer.appendChild(shell);
}

function computeTravelLayout(hexes) {
  const size = 34;
  const rawPoints = (hexes || []).map(hex => ({
    coord: hex.coord,
    x: Math.sqrt(3) * size * (hex.coord.q + hex.coord.r / 2),
    y: size * 1.5 * hex.coord.r,
  }));
  const minX = rawPoints.length ? Math.min(...rawPoints.map(point => point.x)) - size : 0;
  const minY = rawPoints.length ? Math.min(...rawPoints.map(point => point.y)) - size : 0;
  const maxX = rawPoints.length ? Math.max(...rawPoints.map(point => point.x)) + size * 2 : 480;
  const maxY = rawPoints.length ? Math.max(...rawPoints.map(point => point.y)) + size * 2 : 320;
  return {
    size,
    minX,
    minY,
    width: Math.max(480, maxX - minX + 24),
    height: Math.max(320, maxY - minY + 24),
  };
}

function travelHexPixel(coord, minX, minY) {
  const size = 34;
  return {
    left: Math.sqrt(3) * size * (coord.q + coord.r / 2) - minX,
    top: size * 1.5 * coord.r - minY,
  };
}

function renderInspection() {
  els.inspectionPanel.innerHTML = '';
  const inspection = state.inspection;
  if (!inspection) {
    if (state.view?.travel) {
      els.inspectionPanel.textContent = 'Click a hex to inspect it and preview a route.';
      return;
    }
    els.inspectionPanel.textContent = state.view?.runtime_mode === 'character-creation'
      ? 'Character creation is active. Use the command box for /create commands; inspection becomes available once the campaign begins.'
      : 'Click a cell to inspect it.';
    return;
  }
  if (inspection.coord && !inspection.position) {
    renderTravelInspection(inspection);
    return;
  }
  renderBattlefieldInspection(inspection);
}

function renderTravelInspection(inspection) {
  const travel = state.view?.travel;
  const landmarkNames = new Map((travel?.landmarks || []).map(landmark => [landmark.landmark_id, landmark.name]));
  const blocks = [];
  blocks.push(renderKeyValueBlock('Hex', [
    `Coordinates: (${inspection.coord.q}, ${inspection.coord.r})`,
    `Terrain: ${inspection.terrain_id}`,
    `Travel cost: ${inspection.travel_cost_units}`,
    `Route kind: ${inspection.route_kind || 'none'}`,
    `Traversable: ${inspection.traversable}`,
    `Discovered: ${inspection.discovered}`,
    `Location: ${inspection.location_id || 'unknown'}`,
    `Reachable by known route: ${inspection.reachable_by_known_route}`,
  ]));
  if (inspection.landmark_ids?.length) {
    blocks.push(renderInlineBlock('Landmarks', inspection.landmark_ids.map(id => landmarkNames.get(id) || id)));
  }
  if (inspection.tags?.length) {
    blocks.push(renderInlineBlock('Tags', inspection.tags));
  }
  const preview = state.pathPreview;
  if (preview && preview.destination && preview.destination.q !== undefined) {
    blocks.push(renderKeyValueBlock('Route Preview', [
      `Destination: ${preview.destination_label}`,
      `Estimated cost: ${preview.estimated_cost_units}`,
      `Estimated minutes: ${preview.estimated_minutes}`,
      `Path: ${(preview.path || []).map(step => `(${step.q},${step.r})`).join(' -> ') || 'none'}`,
    ]));
  }
  const actionBlock = create('div', 'inspection-block');
  actionBlock.appendChild(create('strong', null, 'Travel Actions'));
  const planButton = create('button', null, 'Plan Route Here');
  planButton.type = 'button';
  planButton.disabled = !inspection.traversable;
  planButton.addEventListener('click', () => sendJson({ type: 'travel_plan_route', q: inspection.coord.q, r: inspection.coord.r }));
  actionBlock.appendChild(planButton);
  if (travel?.pending_hook && state.view?.role === 'dm') {
    const engageButton = create('button', 'secondary', 'Engage Pending Hook');
    engageButton.type = 'button';
    engageButton.addEventListener('click', () => sendJson({ type: 'travel_engage' }));
    actionBlock.appendChild(engageButton);
  }
  blocks.push(actionBlock);
  blocks.forEach(block => els.inspectionPanel.appendChild(block));
}

function renderBattlefieldInspection(inspection) {
  const blocks = [];
  blocks.push(renderKeyValueBlock('Tile', [
    `Coordinates: (${inspection.position.x}, ${inspection.position.y}, ${inspection.position.z})`,
    `Terrain: ${inspection.terrain_id}`,
    `Elevation: ${inspection.elevation_ft} ft`,
    `Traversable: ${inspection.traversable}`,
    `Occupiable: ${inspection.occupiable}`,
    `Movement cost per 5 ft: ${inspection.movement_cost_feet_per_5ft}`,
    `Difficult terrain: ${inspection.difficult_terrain}`,
    `Lighting: ${inspection.lighting}`,
    `Obscurement: ${inspection.obscurement}`,
    `Blocks LOS: ${inspection.blocks_los}`,
    `Blocks LOE: ${inspection.blocks_loe}`,
    `Base cover: ${inspection.base_cover}`,
  ]));
  if (inspection.tags?.length) blocks.push(renderInlineBlock('Tags', inspection.tags));
  if (inspection.apparent_blocked || inspection.apparent_cover || inspection.apparent_tags?.length) {
    blocks.push(renderKeyValueBlock('Apparent', [
      `Apparent blocker: ${inspection.apparent_blocked}`,
      `Apparent cover: ${inspection.apparent_cover || 'none'}`,
      `Apparent tags: ${(inspection.apparent_tags || []).join(', ') || 'none'}`,
    ]));
  }
  if (inspection.feature_ids?.length) blocks.push(renderInlineBlock('Features', inspection.feature_ids));
  if (inspection.feature_summaries?.length) blocks.push(renderKeyValueBlock('Projected Features', inspection.feature_summaries));
  if (inspection.object_ids?.length || inspection.blocker_ids?.length) {
    blocks.push(renderKeyValueBlock('Objects', [
      `Objects: ${(inspection.object_ids || []).join(', ') || 'none'}`,
      `Blockers: ${(inspection.blocker_ids || []).join(', ') || 'none'}`,
    ]));
  }
  if (inspection.edge_summaries?.length) blocks.push(renderKeyValueBlock('Edges', inspection.edge_summaries));
  if (inspection.traversal_views?.length) {
    const block = create('div', 'inspection-block');
    block.appendChild(create('strong', null, 'Movement Modes'));
    for (const traversal of inspection.traversal_views) {
      const row = create('div', 'muted', `${traversal.mode_id}: ${traversal.outcome}; ${traversal.detail}`);
      block.appendChild(row);
    }
    if (state.pathPreview && state.pathPreview.actor_id) {
      const button = create('button', null, `Propose move (${state.previewMode})`);
      button.disabled = !canPreviewMove();
      button.addEventListener('click', () => {
        sendJson({
          type: 'move_proposal',
          x: inspection.position.x,
          y: inspection.position.y,
          z: inspection.position.z,
          mode: state.previewMode,
        });
      });
      block.appendChild(button);
    }
    blocks.push(block);
  }
  if (inspection.teleport_views?.length) {
    const block = create('div', 'inspection-block');
    block.appendChild(create('strong', null, 'Teleport Legality'));
    for (const teleport of inspection.teleport_views) {
      block.appendChild(create('div', 'muted', `${teleport.capability_name}: ${teleport.legal ? 'legal' : 'illegal'}; ${teleport.detail}`));
    }
    blocks.push(block);
  }
  if (state.pathPreview && state.pathPreview.actor_id) {
    blocks.push(renderKeyValueBlock('Path Preview', [
      `Outcome: ${state.pathPreview.outcome}`,
      `Detail: ${state.pathPreview.detail}`,
      `Cost: ${state.pathPreview.total_cost_ft ?? 'n/a'} ft`,
      `Path: ${(state.pathPreview.path || []).map(step => `(${step.x},${step.y},${step.z})`).join(' -> ') || 'none'}`,
    ]));
  }
  blocks.forEach(block => els.inspectionPanel.appendChild(block));
}

function renderInlineBlock(title, values) {
  const block = create('div', 'inspection-block');
  block.appendChild(create('strong', null, title));
  const list = create('div', 'inline-list');
  for (const value of values) list.appendChild(create('span', 'inline-pill', value));
  block.appendChild(list);
  return block;
}

function renderKeyValueBlock(title, lines) {
  const block = create('div', 'inspection-block');
  block.appendChild(create('strong', null, title));
  for (const line of lines) block.appendChild(create('div', 'muted', line));
  return block;
}

function autoScrollChatLog() {
  requestAnimationFrame(() => {
    els.chatLog.scrollTop = els.chatLog.scrollHeight;
  });
}

function renderChat() {
  els.chatLog.innerHTML = '';
  const authoritativeEntries = state.view?.chat_entries || [];
  const entries = buildChatRenderEntries(state.chatFeed, authoritativeEntries);
  if (!entries.length && state.view?.runtime_mode === 'character-creation') {
    els.chatLog.textContent = 'Character creation is active. Use the command box for /create commands. Story narration will appear here after all four players confirm characters.';
    return;
  }
  if (!entries.length) {
    els.chatLog.textContent = 'No chat or narration yet.';
    return;
  }
  for (const entry of entries) {
    const node = create('div', `chat-entry ${entry.category}`);
    node.appendChild(create('div', 'speaker', entry.speaker));
    node.appendChild(create('div', null, entry.text));
    els.chatLog.appendChild(node);
  }
  autoScrollChatLog();
}


function renderCharacterCard() {
  const panel = els.characterCardPanel;
  const select = els.characterCardSelect;
  if (!panel || !select) return;
  panel.innerHTML = '';
  const cards = state.view?.character_cards || [];
  if (!cards.length) {
    select.innerHTML = '';
    select.style.display = 'none';
    panel.textContent = state.view?.runtime_mode === 'character-creation'
      ? 'Character cards become available after confirmed player characters enter the campaign.'
      : 'No player character card is available for this controller.';
    return;
  }
  if (!state.selectedCharacterCardActorId || !cards.some(card => card.actor_id === state.selectedCharacterCardActorId)) {
    state.selectedCharacterCardActorId = cards[0].actor_id;
  }
  if (cards.length > 1) {
    select.innerHTML = '';
    for (const card of cards) {
      const option = document.createElement('option');
      option.value = card.actor_id;
      option.textContent = card.name;
      select.appendChild(option);
    }
    select.value = state.selectedCharacterCardActorId;
    select.style.display = 'inline-flex';
  } else {
    select.innerHTML = '';
    select.style.display = 'none';
  }
  const card = cards.find(item => item.actor_id === state.selectedCharacterCardActorId) || cards[0];
  panel.appendChild(buildCharacterCard(card));
}

function buildCharacterCard(card) {
  const shell = create('div', 'character-card');
  const header = create('div', 'character-header');
  header.appendChild(create('div', 'character-avatar', card.avatar_label || '?'));
  const identity = create('div', 'character-identity');
  identity.appendChild(create('strong', null, card.name));
  const subtitleParts = [
    [card.class_name, card.level ? `Level ${card.level}` : null].filter(Boolean).join(' '),
    card.species_name,
    card.background_name,
  ].filter(Boolean);
  if (subtitleParts.length) {
    identity.appendChild(create('div', 'muted', subtitleParts.join(' | ')));
  }
  if (card.origin_feats?.length) {
    const featLine = create('div', 'muted', `Origin feats: ${card.origin_feats.join(', ')}`);
    identity.appendChild(featLine);
  }
  header.appendChild(identity);
  shell.appendChild(header);

  const statGrid = create('div', 'character-stat-grid');
  statGrid.appendChild(buildStatPill('HP', `${card.current_hit_points ?? '--'}/${card.max_hit_points ?? '--'}`));
  statGrid.appendChild(buildStatPill('Temp', `${card.temp_hit_points ?? 0}`));
  statGrid.appendChild(buildStatPill('AC', `${card.armor_class ?? '--'}`));
  statGrid.appendChild(buildStatPill('PB', formatSigned(card.proficiency_bonus)));
  statGrid.appendChild(buildStatPill('Init', formatSigned(card.initiative_bonus)));
  statGrid.appendChild(buildStatPill('Passive Perception', `${card.passive_perception ?? '--'}`));
  shell.appendChild(statGrid);

  if (card.dying_status || card.death_save_successes !== null || card.death_save_failures !== null || card.stable_recovery_hours_remaining !== null) {
    const dyingLines = [];
    if (card.dying_status) dyingLines.push(`State: ${formatDyingStatus(card.dying_status)}`);
    if (card.death_save_successes !== null && card.death_save_successes !== undefined && card.death_save_failures !== null && card.death_save_failures !== undefined) {
      dyingLines.push(`Death saves: ${card.death_save_successes} success, ${card.death_save_failures} failure`);
    }
    if (card.stable_recovery_hours_remaining !== null && card.stable_recovery_hours_remaining !== undefined) {
      dyingLines.push(`Stable recovery: ${card.stable_recovery_hours_remaining} hour(s)`);
    }
    shell.appendChild(buildCharacterSection('Dying', buildDetailList(dyingLines, 'No dying-state details.')));
  }

  if (state.view?.runtime_mode === 'combat') {
    const combatGrid = create('div', 'character-stat-grid');
    combatGrid.appendChild(buildStatPill('Turn', card.active_turn ? 'Active' : 'Waiting'));
    combatGrid.appendChild(buildStatPill('Move', `${card.movement_remaining_ft ?? '--'} ft`));
    combatGrid.appendChild(buildStatPill('Action', availabilityLabel(card.action_available)));
    combatGrid.appendChild(buildStatPill('Bonus', availabilityLabel(card.bonus_action_available)));
    combatGrid.appendChild(buildStatPill('Reaction', availabilityLabel(card.reaction_available)));
    combatGrid.appendChild(buildStatPill('Object', availabilityLabel(card.free_object_interaction_available)));
    shell.appendChild(combatGrid);
  }

  shell.appendChild(buildCharacterSection('Speeds', buildPillList((card.speeds || []).map(speed => `${speed.label} ${speed.speed_ft} ft`))));
  shell.appendChild(buildAbilitySection(card));
  shell.appendChild(buildSkillSection(card));
  shell.appendChild(buildCharacterSection('Conditions', buildPillList(card.conditions || [], 'No conditions.')));

  const effectLines = [];
  if (card.concentration_effect_name) {
    effectLines.push(`Concentrating on ${card.concentration_effect_name}`);
  }
  for (const effect of card.effects || []) {
    const durationText = effect.remaining_rounds !== null && effect.remaining_rounds !== undefined ? ` (${effect.remaining_rounds} rounds)` : '';
    effectLines.push(`${effect.name}: ${effect.summary}${durationText}`);
  }
  shell.appendChild(buildCharacterSection('Effects', buildDetailList(effectLines, 'No active effects.')));

  const attackLines = (card.attacks || []).map(attack => {
    const rangeBits = [];
    if (attack.reach_ft) rangeBits.push(`reach ${attack.reach_ft} ft`);
    if (attack.range_ft) rangeBits.push(`range ${attack.range_ft} ft`);
    if (attack.long_range_ft) rangeBits.push(`long ${attack.long_range_ft} ft`);
    const rangeText = rangeBits.length ? `; ${rangeBits.join(', ')}` : '';
    return `${attack.name}: ${formatSigned(attack.to_hit_bonus)} to hit; ${attack.damage_text}${rangeText}`;
  });
  shell.appendChild(buildCharacterSection('Attacks', buildDetailList(attackLines, 'No attack summary available.')));

  const itemLines = [
    `Main hand: ${card.main_hand_label || 'Empty'}`,
    `Off hand: ${card.off_hand_label || 'Empty'}`,
    `Armor: ${card.armor_label || 'None'}`,
    ...((card.items || []).map(item => {
      const stateLabel = item.state_label ? ` [${item.state_label}]` : '';
      return `${item.label} x${item.quantity}${stateLabel}`;
    })),
  ];
  shell.appendChild(buildCharacterSection('Equipment', buildDetailList(itemLines, 'No important carried items tracked.')));

  if (card.spellcasting_ability || (card.cantrips || []).length || (card.spells || []).length || card.spell_save_dc !== null || card.spell_attack_bonus !== null) {
    const spellNodes = create('div', 'character-spell-block');
    if (card.spellcasting_ability || card.spell_save_dc !== null || card.spell_attack_bonus !== null) {
      const summary = [];
      if (card.spellcasting_ability) summary.push(`Ability: ${card.spellcasting_ability}`);
      if (card.spell_save_dc !== null && card.spell_save_dc !== undefined) summary.push(`Save DC: ${card.spell_save_dc}`);
      if (card.spell_attack_bonus !== null && card.spell_attack_bonus !== undefined) summary.push(`Attack: ${formatSigned(card.spell_attack_bonus)}`);
      spellNodes.appendChild(create('div', 'muted', summary.join(' | ')));
    }
    if ((card.cantrips || []).length) {
      spellNodes.appendChild(buildDetailList((card.cantrips || []).map(formatSpellLine), 'No cantrips selected.'));
    }
    if ((card.spells || []).length) {
      spellNodes.appendChild(buildDetailList((card.spells || []).map(formatSpellLine), 'No leveled spells selected.'));
    }
    shell.appendChild(buildCharacterSection('Spellcasting', spellNodes));
  }

  const resourceLines = (card.resources || []).map(resource => `${resource.label}: ${resource.remaining_uses ?? '--'} (${resource.detail})`);
  if (resourceLines.length) {
    shell.appendChild(buildCharacterSection('Resources', buildDetailList(resourceLines, 'No tracked limited-use resources.')));
  }

  const featAndToolLines = [];
  if (card.feat_summaries?.length) featAndToolLines.push(`Feat grants: ${card.feat_summaries.join(', ')}`);
  if (card.tool_proficiencies?.length) featAndToolLines.push(`Tools: ${card.tool_proficiencies.join(', ')}`);
  if (featAndToolLines.length) {
    shell.appendChild(buildCharacterSection('Proficiencies', buildDetailList(featAndToolLines, 'No extra feat or tool summary.')));
  }

  return shell;
}

function formatDyingStatus(value) {
  if (!value) return 'Alive';
  return value
    .split('-')
    .filter(Boolean)
    .map(part => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function buildStatPill(label, value) {
  const node = create('div', 'character-stat-pill');
  node.appendChild(create('div', 'pill-label', label));
  node.appendChild(create('div', 'pill-value', value));
  return node;
}

function buildCharacterSection(title, contentNode) {
  const section = create('section', 'character-section');
  section.appendChild(create('h3', null, title));
  section.appendChild(contentNode);
  return section;
}

function buildAbilitySection(card) {
  const grid = create('div', 'character-ability-grid');
  for (const ability of card.abilities || []) {
    const row = create('div', 'character-line-item');
    row.appendChild(create('strong', null, `${ability.label}: ${ability.score} (${formatSigned(ability.modifier)})`));
    row.appendChild(create('div', 'muted', `Save ${formatSigned(ability.save_bonus)}${ability.save_proficient ? ' proficient' : ''}`));
    grid.appendChild(row);
  }
  return buildCharacterSection('Abilities', grid);
}

function buildSkillSection(card) {
  const grid = create('div', 'character-skill-grid');
  if (!(card.skills || []).length) {
    grid.textContent = 'No skill summary available.';
  }
  for (const skill of card.skills || []) {
    const row = create('div', 'character-line-item');
    row.appendChild(create('strong', null, `${skill.label} ${formatSigned(skill.bonus)}`));
    row.appendChild(create('div', 'muted', skill.proficient ? 'proficient' : 'not proficient'));
    grid.appendChild(row);
  }
  return buildCharacterSection('Skills', grid);
}

function buildPillList(values, emptyText = 'None.') {
  if (!values.length) return create('div', 'muted', emptyText);
  const list = create('div', 'inline-list');
  for (const value of values) list.appendChild(create('span', 'inline-pill', value));
  return list;
}

function buildDetailList(values, emptyText) {
  const block = create('div', 'character-detail-list');
  if (!values.length) {
    block.appendChild(create('div', 'muted', emptyText));
    return block;
  }
  for (const value of values) block.appendChild(create('div', 'muted', value));
  return block;
}

function formatSigned(value) {
  if (value === null || value === undefined) return '--';
  if (value > 0) return `+${value}`;
  return `${value}`;
}

function availabilityLabel(value) {
  if (value === null || value === undefined) return '--';
  return value ? 'Ready' : 'Spent';
}

function formatSpellLine(spell) {
  const details = [`L${spell.level}`, spell.selection_kind, spell.source_label];
  if (spell.remaining_uses !== null && spell.remaining_uses !== undefined) {
    details.push(`uses ${spell.remaining_uses}`);
  }
  return `${spell.name}: ${details.join(' | ')}`;
}

function renderActions() {
  els.actionPanel.innerHTML = '';
  const groups = state.view?.action_groups || [];
  if (!groups.length) {
    if (state.view?.runtime_mode === 'character-creation') {
      els.actionPanel.textContent = 'Use /create commands in the command box. Available choice pools will appear here when the current step exposes option ids.';
      return;
    }
    els.actionPanel.textContent = 'No active actions available. Use the chat box for storytelling declarations or wait for your turn.';
    return;
  }
  for (const group of groups) {
    const groupNode = create('div', 'choice-group');
    groupNode.appendChild(create('h3', null, group.label));
    for (const choice of group.choices) {
      const item = create('div', `choice-item ${state.pendingAction?.group_id === choice.group_id && state.pendingAction?.option_id === choice.option_id ? 'pending' : ''}`);
      item.appendChild(create('strong', null, choice.label));
      item.appendChild(create('div', 'detail', choice.detail));
      if (choice.command_hint) item.appendChild(create('div', 'detail', `Hint: ${choice.command_hint}`));
      const controls = create('div', 'inline-list');
      const button = create('button', choice.execution_kind === 'creation-choice' ? 'secondary' : null, actionButtonLabel(choice));
      button.disabled = false;
      button.addEventListener('click', () => handleChoice(choice));
      controls.appendChild(button);
      if (choice.execution_kind === 'creation-choice' && choice.command_insert_text) {
        const commandButton = create('button', null, 'Insert command');
        commandButton.addEventListener('click', () => insertCreationCommand(choice));
        controls.appendChild(commandButton);
      }
      item.appendChild(controls);
      groupNode.appendChild(item);
    }
    els.actionPanel.appendChild(groupNode);
  }
}

function actionButtonLabel(choice) {
  if (choice.execution_kind === 'creation-choice') return 'Insert id';
  if (choice.target_kind === 'creature') return 'Choose target';
  if (choice.target_kind === 'point' || choice.target_kind === 'area') return 'Choose map point';
  return 'Send';
}

function handleChoice(choice) {
  if (choice.execution_kind === 'creation-choice') {
    insertChoiceId(choice.option_id);
    return;
  }
  if (choice.target_kind === 'creature' || choice.target_kind === 'point' || choice.target_kind === 'area') {
    state.pendingAction = choice;
    renderActions();
    appendSystemEntry('system', `Select a ${choice.target_kind} for ${choice.label}.`);
    return;
  }
  sendActionProposal({ group_id: choice.group_id, option_id: choice.option_id });
}

function insertChoiceId(optionId) {
  const current = els.commandInput.value.trimEnd();
  els.commandInput.value = current ? `${current} ${optionId}` : optionId;
  els.commandInput.focus();
  appendSystemEntry('system', `Inserted ${optionId} into the command box.`);
}

function insertCreationCommand(choice) {
  const commandText = choice.command_insert_text;
  if (!commandText) {
    insertChoiceId(choice.option_id);
    return;
  }
  const prefix = choice.command_prefix;
  const current = els.commandInput.value.trim();
  if (prefix && current.startsWith(prefix)) {
    const tokens = current.split(/\s+/);
    if (!tokens.includes(choice.option_id)) {
      els.commandInput.value = `${current} ${choice.option_id}`;
      els.commandInput.focus();
      appendSystemEntry('system', `Appended ${choice.option_id} to the current /create command.`);
      return;
    }
  }
  els.commandInput.value = commandText;
  els.commandInput.focus();
  appendSystemEntry('system', `Inserted ${commandText} into the command box.`);
}

function sendActionProposal(payload) {
  sendJson({ type: 'action_proposal', ...payload });
  state.pendingAction = null;
  renderActions();
}

function renderPrompt() {
  els.promptPanel.innerHTML = '';
  const prompt = state.prompt;
  if (!prompt) {
    els.promptPanel.textContent = state.view?.runtime_mode === 'character-creation'
      ? 'No pending prompt during character creation.'
      : 'No pending prompt.';
    return;
  }
  const block = create('div', 'inspection-block');
  block.appendChild(create('strong', null, prompt.prompt_kind));
  prompt.text.split('\n').forEach(line => block.appendChild(create('div', 'muted', line)));
  if (prompt.prompt_kind === 'story-check') {
    const button = create('button', null, 'Resolve /check');
    button.addEventListener('click', () => sendCommand('/check'));
    block.appendChild(button);
  }
  for (const option of prompt.options || []) {
    const optionNode = create('div', 'prompt-option');
    optionNode.appendChild(create('strong', null, option.label));
    optionNode.appendChild(create('div', 'detail', option.detail));
    const button = create('button', null, 'Choose');
    button.addEventListener('click', () => sendJson({ type: 'reaction', option_ids: [option.option_id] }));
    optionNode.appendChild(button);
    block.appendChild(optionNode);
  }
  if (prompt.options?.length) {
    const decline = create('button', 'secondary', 'Decline');
    decline.addEventListener('click', () => sendJson({ type: 'reaction', option_ids: [] }));
    block.appendChild(decline);
  }
  els.promptPanel.appendChild(block);
}

function renderSummary() {
  els.summaryPanel.innerHTML = '';
  const lines = state.view?.summary_lines || [];
  if (!lines.length) {
    els.summaryPanel.textContent = 'No summary available yet.';
    return;
  }
  for (const line of lines) {
    els.summaryPanel.appendChild(create('div', 'muted', line));
  }
}

function canPreviewMove() {
  const view = state.view;
  if (!view) return false;
  if (view.runtime_mode !== 'combat') return false;
  return (view.owned_actor_ids || []).includes(view.active_actor_id);
}

function initializeMapPanning() {
  const container = els.mapContainer;
  const pan = state.mapPan;

  function stopPanning() {
    if (!pan.active) return;
    pan.active = false;
    container.classList.remove('panning');
  }

  container.addEventListener('mousedown', event => {
    if (event.button !== 2) return;
    pan.active = true;
    pan.moved = false;
    pan.startX = event.clientX;
    pan.startY = event.clientY;
    pan.scrollLeft = container.scrollLeft;
    pan.scrollTop = container.scrollTop;
    container.classList.add('panning');
    event.preventDefault();
  });

  window.addEventListener('mousemove', event => {
    if (!pan.active) return;
    const deltaX = event.clientX - pan.startX;
    const deltaY = event.clientY - pan.startY;
    if (Math.abs(deltaX) > 2 || Math.abs(deltaY) > 2) {
      pan.moved = true;
    }
    container.scrollLeft = pan.scrollLeft - deltaX;
    container.scrollTop = pan.scrollTop - deltaY;
  });

  window.addEventListener('mouseup', () => {
    stopPanning();
  });

  window.addEventListener('blur', stopPanning);

  container.addEventListener('contextmenu', event => {
    if (pan.active || pan.moved) {
      event.preventDefault();
    }
    pan.moved = false;
  });
}

els.characterCardSelect?.addEventListener('change', () => {
  state.selectedCharacterCardActorId = els.characterCardSelect.value || null;
  renderCharacterCard();
});

els.controllerId.addEventListener('change', () => {
  if (!els.controllerToken.value || els.controllerToken.value.endsWith('-token')) {
    els.controllerToken.value = defaultTokenForController(els.controllerId.value);
  }
});
els.connectButton.addEventListener('click', connect);
els.disconnectButton.addEventListener('click', disconnect);
els.sendCommandButton.addEventListener('click', () => sendCommand(els.commandInput.value));
els.resolveCheckButton.addEventListener('click', () => sendCommand('/check'));
els.commandInput.addEventListener('keydown', event => {
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
    sendCommand(els.commandInput.value);
  }
});

initializeMapPanning();
loadConfig()
  .then(() => {
    renderAll();
    if (state.autoConnect) {
      connect();
    }
  })
  .catch(error => appendSystemEntry('error', `Failed to load frontend config: ${error}`));
renderAll();






