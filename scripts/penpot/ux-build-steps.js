// Penpot MCP execute_code steps for Personal AI current UX.
// Run sequentially via Penpot MCP execute_code when the plugin bridge is connected.
// Each step must return a JSON-serializable value (no functions).

export const UX_BUILD_STEPS = [
  // Step 0 — helpers in storage
  `storage.C = {
  bg: '#F5F5F7', elevated: '#FFFFFF', panel: '#FFFFFF', panelStrong: '#E8E8ED',
  border: '#D2D2D7', borderStrong: '#C7C7CC', focus: '#007AFF',
  text: '#1D1D1F', bright: '#000000', dim: '#6E6E73',
};
storage.H = {
  rect(parent, o) {
    const r = penpot.createRectangle();
    r.name = o.name; r.resize(o.w, o.h);
    r.fills = o.fill ? [{ fillColor: o.fill, fillOpacity: 1 }] : [];
    if (o.radius) r.borderRadius = o.radius;
    if (o.stroke) r.strokes = [{ strokeColor: o.stroke, strokeStyle: 'solid', strokeWidth: 1, strokeAlignment: 'center' }];
    parent.appendChild(r);
    if (o.lc) Object.assign(r.layoutChild, o.lc);
    return r;
  },
  text(parent, o) {
    const t = penpot.createText(o.text);
    t.name = o.name; t.growType = o.grow || 'auto-width';
    t.fontSize = String(o.size || 14); t.fontFamily = 'Inter';
    t.fontWeight = o.weight || '400';
    t.fills = [{ fillColor: o.color || storage.C.text, fillOpacity: 1 }];
    parent.appendChild(t);
    if (o.lc) Object.assign(t.layoutChild, o.lc);
    return t;
  },
  board(parent, o) {
    const b = penpot.createBoard();
    b.name = o.name; b.resize(o.w, o.h);
    b.fills = o.fill ? [{ fillColor: o.fill, fillOpacity: 1 }] : [];
    if (o.radius) b.borderRadius = o.radius;
    if (o.stroke) b.strokes = [{ strokeColor: o.stroke, strokeStyle: 'solid', strokeWidth: 1, strokeAlignment: 'center' }];
    parent.appendChild(b);
    if (o.lc) Object.assign(b.layoutChild, o.lc);
    return b;
  },
};
return 'helpers';`,

  // Step 1 — Desktop Light shell
  `const page = penpotUtils.getPageByName('Desktop — Light');
penpot.openPage(page);
penpotUtils.findShapes(() => true, penpot.root).forEach((s) => s.remove());
const C = storage.C; const H = storage.H;
const app = H.board(penpot.root, { name: 'App / Desktop 1440', w: 1440, h: 900, fill: C.bg });
app.x = 80; app.y = 80;
penpotUtils.addFlexLayout(app, 'row');
app.flex.alignItems = 'stretch';
app.flex.horizontalSizing = 'fix';
app.flex.verticalSizing = 'fix';
storage.app = app;
return 'light-shell';`,

  // Step 2 — Sidebar
  `const C = storage.C; const H = storage.H; const app = storage.app;
const sidebar = H.board(app, { name: 'Sidebar', w: 280, h: 900, fill: C.panel, stroke: C.borderStrong, lc: { verticalSizing: 'fill' } });
penpotUtils.addFlexLayout(sidebar, 'column');
sidebar.flex.rowGap = 12; sidebar.flex.topPadding = 16; sidebar.flex.leftPadding = 16; sidebar.flex.rightPadding = 16;
sidebar.flex.verticalSizing = 'fill';
H.text(sidebar, { name: 'App title', text: 'Smart Chat', size: 14, weight: '600', color: C.bright });
const newChat = H.board(sidebar, { name: 'New conversation', w: 248, h: 44, fill: C.panelStrong, stroke: C.border, radius: 10 });
H.text(newChat, { name: 'Label', text: 'New conversation', size: 14, weight: '500', color: C.text });
penpotUtils.setParentXY(penpotUtils.findShape((s) => s.name === 'Label', newChat), 16, 12);
H.text(sidebar, { name: 'Recent label', text: 'RECENT', size: 10, color: C.dim });
const item = H.board(sidebar, { name: 'Conversation active', w: 248, h: 52, fill: C.elevated, stroke: C.focus, radius: 8, lc: { horizontalSizing: 'fill' } });
H.text(item, { name: 'Title', text: 'What should I pack for Kansas...', size: 12, weight: '500', color: C.text, grow: 'auto-height' });
penpotUtils.setParentXY(penpotUtils.findShape((s) => s.name === 'Title', item), 8, 8);
H.text(item, { name: 'Meta', text: 'Today · 4 messages', size: 10, color: C.dim, grow: 'auto-height' });
penpotUtils.setParentXY(penpotUtils.findShape((s) => s.name === 'Meta', item), 8, 28);
storage.sidebar = sidebar;
return 'sidebar';`,

  // Step 3 — Main area
  `const C = storage.C; const H = storage.H; const app = storage.app;
const main = H.board(app, { name: 'Main', w: 1160, h: 900, fill: C.panelStrong, lc: { verticalSizing: 'fill', horizontalSizing: 'fill' } });
penpotUtils.addFlexLayout(main, 'column');
main.flex.verticalSizing = 'fill';
const header = H.board(main, { name: 'Chat header', w: 1160, h: 72, fill: C.panel, stroke: C.border, lc: { horizontalSizing: 'fill' } });
H.text(header, { name: 'Title', text: 'New conversation', size: 16, weight: '600', color: C.bright });
penpotUtils.setParentXY(penpotUtils.findShape((s) => s.name === 'Title', header), 24, 16);
H.text(header, { name: 'Subtitle', text: 'Smart router · chat/rag/workflow', size: 12, color: C.dim });
penpotUtils.setParentXY(penpotUtils.findShape((s) => s.name === 'Subtitle', header), 24, 40);
const content = H.board(main, { name: 'Message log', w: 1160, h: 700, fill: C.panelStrong, lc: { verticalSizing: 'fill', horizontalSizing: 'fill' } });
const empty = H.board(content, { name: 'Empty state', w: 760, h: 280, fill: C.elevated, stroke: C.border, radius: 24 });
penpotUtils.setParentXY(empty, 32, 32);
H.text(empty, { name: 'Eyebrow', text: 'SYSTEM READY', size: 11, color: C.dim });
penpotUtils.setParentXY(penpotUtils.findShape((s) => s.name === 'Eyebrow', empty), 32, 32);
H.text(empty, { name: 'Headline', text: 'Start a smart-routed conversation', size: 28, weight: '600', color: C.bright });
penpotUtils.setParentXY(penpotUtils.findShape((s) => s.name === 'Headline', empty), 32, 56);
const inputBar = H.board(main, { name: 'Chat input bar', w: 1160, h: 88, fill: C.panel, stroke: C.borderStrong, lc: { horizontalSizing: 'fill' } });
const composer = H.board(inputBar, { name: 'Composer', w: 1100, h: 52, fill: C.elevated, stroke: C.border, radius: 16 });
penpotUtils.setParentXY(composer, 24, 16);
H.text(composer, { name: 'Placeholder', text: 'Message Smart Chat…', size: 14, color: C.dim });
penpotUtils.setParentXY(penpotUtils.findShape((s) => s.name === 'Placeholder', composer), 16, 16);
return 'main';`,
];
