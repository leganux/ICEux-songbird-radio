const csrf = document.body.dataset.csrf;
let libraryAssets = [];
let playlists = [];
let carts = [];

function textOrDash(value) {
  return value || '-';
}

function render(state) {
  const now = state.now_playing || {};
  const next = state.next_track || {};
  $('#now-title, #footer-now-title').text(textOrDash(now.title));
  $('#now-artist, #footer-now-artist').text(now.artist || 'ICEux');
  $('#now-meta').text(`${now.type || 'music'} · ${now.source || 'fallback'}`);
  $('#next-title, #footer-next-title').text(next.title || 'Queue is empty');
  $('#next-artist').text(next.artist || 'Local automation');
  $('#next-meta').text(`Origen: ${next.source || 'rotation'}`);

  const list = $('#queue').empty();
  if (!state.queue.length) {
    list.append('<tr><td colspan="4" class="muted">No manual items queued.</td></tr>');
  }
  state.queue.forEach((item, index) => {
    const remove = $('<button>Remove</button>');
    remove.on('click', async () => {
      const result = await fetch(`/api/queue/${item.id}`, { method: 'DELETE', headers: { 'X-CSRF-Token': csrf } });
      if (!result.ok) alert((await result.json()).detail || 'Could not remove item');
      await refreshRadioState();
    });
    list.append(
      $('<tr>')
        .append($('<td>').text(index + 1))
        .append($('<td>').text(item.type))
        .append($('<td>').text(`${item.title} `).append($('<small>').text(item.artist)))
        .append($('<td>').text(item.source || 'Admin').append(' ').append(remove)),
    );
  });
  renderHistory(state.history || []);
}

function formatDuration(seconds) {
  if (!seconds) return '-';
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60).toString().padStart(2, '0');
  return `${mins}:${secs}`;
}

function storageLabel(asset) {
  const status = asset.metadata && asset.metadata.storage;
  if (!status) return 'local';
  if (status === 'uploaded') return 'local + minio';
  if (status.startsWith('degraded')) return 'local only';
  return status;
}

function filteredAssets() {
  const query = ($('#library-search').val() || '').toLowerCase().trim();
  if (!query) return libraryAssets;
  return libraryAssets.filter((asset) => [asset.title, asset.artist, asset.type, asset.tags].join(' ').toLowerCase().includes(query));
}

function renderLibrary() {
  const body = $('#library').empty();
  const assets = filteredAssets();
  if (!assets.length) {
    body.append('<tr><td colspan="6" class="muted">No audio found.</td></tr>');
    return;
  }
  assets.forEach((asset, index) => {
    const action = $('<button>Automation</button>');
    action.on('click', async () => {
      const result = await fetch(`/api/library/${asset.id}/automation`, { method: 'POST', headers: { 'X-CSRF-Token': csrf } });
      if (!result.ok) alert((await result.json()).detail || 'Could not update automation playlist');
    });
    const playNext = $('<button class="ml-1">Play next</button>');
    playNext.on('click', async () => {
      const result = await fetch('/api/queue', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
        body: JSON.stringify({ asset_id: asset.id, source: 'manual', insertion_policy: 'play_next' }),
      });
      if (!result.ok) alert((await result.json()).detail || 'Could not queue asset');
      await refreshRadioState();
    });
    body.append(
      $('<tr>')
        .append($('<td>').text(index + 1))
        .append($('<td>').text(asset.artist ? `${asset.title} - ${asset.artist}` : asset.title))
        .append($('<td>').text(asset.type))
        .append($('<td>').text(formatDuration(asset.duration)))
        .append($('<td>').text(storageLabel(asset)))
        .append($('<td>').append(action).append(playNext)),
    );
  });
}

async function loadLibrary() {
  const response = await fetch('/api/library');
  libraryAssets = await response.json();
  renderLibrary();
}

function renderPlaylistSelects() {
  $('.playlist-asset-select').each(function updateAssetSelect() {
    const selected = $(this).val();
    $(this).empty();
    libraryAssets.forEach((asset) => $(this).append($('<option>').val(asset.id).text(asset.artist ? `${asset.title} - ${asset.artist}` : asset.title)));
    if (selected) $(this).val(selected);
  });
  const scheduleSelect = $('#schedule-playlist').empty();
  scheduleSelect.append($('<option>').val('').text('No playlist'));
  playlists.forEach((playlist) => scheduleSelect.append($('<option>').val(playlist.id).text(playlist.name)));
  const cartSelect = $('#cart-asset').empty();
  cartSelect.append($('<option>').val('').text('No asset'));
  libraryAssets.forEach((asset) => cartSelect.append($('<option>').val(asset.id).text(asset.artist ? `${asset.title} - ${asset.artist}` : asset.title)));
}

async function loadPlaylists() {
  const response = await fetch('/api/playlists');
  playlists = await response.json();
  const container = $('#playlists').empty().removeClass('muted');
  if (!playlists.length) {
    container.addClass('muted').text('No playlists yet.');
    renderPlaylistSelects();
    return;
  }
  playlists.forEach((playlist) => {
    const assetSelect = $('<select class="form-control form-control-sm playlist-asset-select mr-2">');
    libraryAssets.forEach((asset) => assetSelect.append($('<option>').val(asset.id).text(asset.artist ? `${asset.title} - ${asset.artist}` : asset.title)));
    const addButton = $('<button class="mr-2">Add</button>');
    addButton.on('click', async () => {
      const assetId = assetSelect.val();
      if (!assetId) return;
      const result = await fetch(`/api/playlists/${playlist.id}/items`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
        body: JSON.stringify({ asset_id: assetId }),
      });
      if (!result.ok) alert((await result.json()).detail || 'Could not add asset');
      await loadPlaylists();
    });
    const materializeButton = $('<button class="danger">Use on air</button>');
    materializeButton.on('click', async () => {
      const result = await fetch(`/api/playlists/${playlist.id}/materialize`, { method: 'POST', headers: { 'X-CSRF-Token': csrf } });
      if (!result.ok) alert((await result.json()).detail || 'Could not materialize playlist');
    });
    const itemText = playlist.items.length ? playlist.items.map((item) => item.asset.title).join(', ') : 'No tracks';
    container.append(
      $('<div class="playlist-card">')
        .append($('<div class="playlist-heading">').append($('<strong>').text(playlist.name)).append($('<small>').text(` ${playlist.rotation_policy}`)))
        .append($('<p class="muted mb-2">').text(itemText))
        .append($('<div class="form-inline">').append(assetSelect).append(addButton).append(materializeButton)),
    );
  });
  renderPlaylistSelects();
}

async function loadCarts() {
  const response = await fetch('/api/carts');
  carts = await response.json();
  const grid = $('#cart-grid').empty();
  if (!carts.length) {
    [
      ['RADIO LEGANUX', 'ID', 'blue'],
      ['APPLAUSE', 'FX', 'orange'],
      ['BREAKING NEWS', 'FX', 'red'],
      ['JINGLE 1', 'Jingle', 'purple'],
      ['JINGLE 2', 'Jingle', 'purple'],
      ['CORTINILLA', 'ID', 'blue'],
      ['COMERCIAL', 'Commercial', 'green'],
      ['SWEEP', 'FX', 'gold'],
      ['EMERGENCY', 'FX', 'red'],
    ].forEach(([label, category, color]) => grid.append($(`<button class="cart ${color}">${label}<span>${category}</span></button>`)));
    return;
  }
  carts.forEach((cart) => {
    const button = $(`<button class="cart ${cart.color}">${cart.label}<span>${cart.category} · ${cart.action}</span></button>`);
    button.on('click', async () => {
      const result = await fetch(`/api/carts/${cart.id}/fire`, { method: 'POST', headers: { 'X-CSRF-Token': csrf } });
      if (!result.ok) alert((await result.json()).detail || 'Could not fire cart');
      await refreshRadioState();
    });
    grid.append(button);
  });
}

function renderHistory(items) {
  const body = $('#history-list').empty();
  if (!items.length) {
    body.append('<tr><td class="muted">No history yet.</td></tr>');
    return;
  }
  items.forEach((item) => {
    const playedAt = new Date(item.played_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    body.append($('<tr>').append($('<td>').text(playedAt)).append($('<td>').text(item.title)).append($('<td>').text(item.source)));
  });
}

async function refreshRadioState() {
  const response = await fetch('/api/radio/state');
  render(await response.json());
}

async function loadSchedules() {
  const response = await fetch('/api/schedules');
  const rules = await response.json();
  const container = $('#schedules').empty().removeClass('muted');
  if (!rules.length) {
    container.addClass('muted').text('No schedule rules yet.');
    return;
  }
  rules.forEach((rule) => {
    container.append(
      $('<div class="schedule-row">')
        .append($('<strong>').text(rule.name))
        .append($('<small>').text(` ${rule.cron} · ${rule.missed_policy}`))
        .append($('<div class="muted">').text(rule.playlist ? rule.playlist.name : rule.event_type)),
    );
  });
}

function updateClock() {
  const now = new Date();
  const time = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const date = now.toLocaleDateString([], { weekday: 'short', month: 'short', day: '2-digit', year: 'numeric' });
  $('#digital-clock, #large-clock').text(time);
  $('#digital-date').text(date);
}

$('#library-search').on('input', renderLibrary);

$('#queue-form').on('submit', async function onQueueSubmit(event) {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(this));
  const response = await fetch('/api/queue', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
    body: JSON.stringify(data),
  });
  if (response.ok) {
    this.reset();
    $('#queueModal').modal('hide');
    render(await (await fetch('/api/radio/state')).json());
  }
});

$('#upload-form').on('submit', async function onUploadSubmit(event) {
  event.preventDefault();
  const button = $(this).find('button').prop('disabled', true).text('Importing...');
  const response = await fetch('/api/library/upload', {
    method: 'POST',
    headers: { 'X-CSRF-Token': csrf },
    body: new FormData(this),
  });
  button.prop('disabled', false).text('Import');
  if (!response.ok) {
    alert((await response.json()).detail || 'Upload failed');
    return;
  }
  this.reset();
  $('#uploadModal').modal('hide');
  await loadLibrary();
  await loadPlaylists();
  await loadCarts();
});

$('#playlist-form').on('submit', async function onPlaylistSubmit(event) {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(this));
  const response = await fetch('/api/playlists', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    alert((await response.json()).detail || 'Could not create playlist');
    return;
  }
  this.reset();
  $('#playlistModal').modal('hide');
  await loadPlaylists();
});

$('#cart-form').on('submit', async function onCartSubmit(event) {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(this));
  const response = await fetch('/api/carts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    alert((await response.json()).detail || 'Could not create cart');
    return;
  }
  this.reset();
  $('#cartModal').modal('hide');
  await loadCarts();
});

$('#schedule-form').on('submit', async function onScheduleSubmit(event) {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(this));
  const response = await fetch('/api/schedules', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    alert((await response.json()).detail || 'Could not create schedule rule');
    return;
  }
  this.reset();
  $('#scheduleModal').modal('hide');
  await loadSchedules();
});

$('#skip').on('click', async () => {
  const response = await fetch('/api/player/skip', { method: 'POST', headers: { 'X-CSRF-Token': csrf } });
  if (!response.ok) alert((await response.json()).detail);
});

fetch('/health')
  .then((response) => response.json())
  .then((health) => {
    const liquidsoapOk = health.components.liquidsoap === 'ok';
    $('#sqlite').text(health.components.sqlite.toUpperCase());
    $('#liquidsoap').text(health.components.liquidsoap.toUpperCase());
    $('#liquidsoap-dot').addClass(liquidsoapOk ? 'ok' : 'warn');
    $('#icecast-status').text(liquidsoapOk ? 'Conectado' : 'Revisar mount');
  });

updateClock();
setInterval(updateClock, 1000);
refreshRadioState();
loadLibrary().then(loadPlaylists).then(loadCarts);
loadSchedules();

const socket = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws/radio');
socket.onmessage = (event) => render(JSON.parse(event.data).data);
setInterval(() => socket.readyState === 1 && socket.send('ping'), 25000);
