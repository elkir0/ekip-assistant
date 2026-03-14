<script>
  import { devialetData, wsConnected, sendWS } from '../stores/assistant.js';

  let statusRequested = false;

  $: if ($wsConnected && !$devialetData && !statusRequested) {
    statusRequested = true;
    sendWS({ type: 'devialet_status' });
  }
  $: if (!$wsConnected) statusRequested = false;

  $: d = $devialetData || {
    connected: false, model: '', systemName: 'Devialet', firmware: '',
    volume: 0, nightMode: false, eqPreset: 'flat', currentSource: null,
    sources: [], devices: []
  };
  $: isMuted = d.volume === 0;

  let volumeTimeout;
  function onVolumeInput(e) {
    const vol = parseInt(e.target.value);
    clearTimeout(volumeTimeout);
    volumeTimeout = setTimeout(() => sendWS({ type: 'devialet_volume', data: vol }), 150);
  }

  function volUp() { sendWS({ type: 'devialet_volume_up' }); }
  function volDown() { sendWS({ type: 'devialet_volume_down' }); }
  function toggleMute() { sendWS({ type: isMuted ? 'devialet_unmute' : 'devialet_mute' }); }
  function play() { sendWS({ type: 'devialet_play' }); }
  function pause() { sendWS({ type: 'devialet_pause' }); }
  function prev() { sendWS({ type: 'devialet_prev' }); }
  function next() { sendWS({ type: 'devialet_next' }); }
  function toggleNight() { sendWS({ type: 'devialet_night_mode', data: !d.nightMode }); }
  function setEq(preset) { sendWS({ type: 'devialet_eq_preset', data: preset }); }

  const sourceLabels = { spotifyconnect: 'Spotify Connect', airplay2: 'AirPlay 2', bluetooth: 'Bluetooth', optical: 'Optique', upnp: 'UPnP', raat: 'Roon' };
  const sourceIcons = {
    spotifyconnect: 'M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z',
    airplay2: 'M6 22h12l-6-6-6 6zM21 3H3c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h4v-2H3V5h18v12h-4v2h4c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2z',
    bluetooth: 'M17.71 7.71L12 2h-1v7.59L6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 11 14.41V22h1l5.71-5.71-4.3-4.29 4.3-4.29zM13 5.83l1.88 1.88L13 9.59V5.83zm1.88 10.46L13 18.17v-3.76l1.88 1.88z',
    optical: 'M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 14H4V6h16v12zM6 10h2v4H6zm3.5 0h1v4h-1zm2.5 0h2v4h-2zm3.5 0h1v4h-1zm2.5 0h2v4h-2z',
    upnp: 'M15 20H5V10H3v10c0 1.1.9 2 2 2h10v-2zm5-18H9c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 12H9V4h11v10z',
    raat: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z'
  };
  function getSourceIcon(src) { return sourceIcons[src] || ''; }
  function getSourceLabel(src) { return sourceLabels[src] || src || 'Veille'; }

  const eqPresets = ['flat', 'custom', 'voice'];
  const eqLabels = { flat: 'Flat', custom: 'Custom', voice: 'Voice' };
</script>

<div class="devialet-page">
  <div class="header">
    <div class="header-left">
      <h1 class="system-name">{d.systemName || 'Devialet'}</h1>
      <span class="model-info">{d.model}{d.firmware ? ' - v' + d.firmware : ''}</span>
    </div>
    <span class="status-dot" class:online={d.connected}></span>
  </div>

  {#if !d.connected}
    <div class="offline-msg">Enceinte non detectee sur le reseau</div>
  {:else}
    <div class="volume-section">
      <div class="volume-circle">
        <span class="volume-number">{d.volume}</span>
        <span class="volume-unit">%</span>
      </div>
      <div class="volume-controls">
        <button class="icon-btn" on:click={volDown} aria-label="Volume -">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M18.5 12c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM5 9v6h4l5 5V4L9 9H5z"/></svg>
        </button>
        <input type="range" min="0" max="100" value={d.volume} on:input={onVolumeInput} class="vol-slider" />
        <button class="icon-btn" on:click={volUp} aria-label="Volume +">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/></svg>
        </button>
      </div>
    </div>

    <div class="source-section">
      <div class="source-info">
        {#if d.currentSource && getSourceIcon(d.currentSource)}
          <svg class="source-icon" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d={getSourceIcon(d.currentSource)} /></svg>
        {:else}
          <svg class="source-icon standby" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M13 3h-2v10h2V3zm4.83 2.17l-1.42 1.42C17.99 7.86 19 9.81 19 12c0 3.87-3.13 7-7 7s-7-3.13-7-7c0-2.19 1.01-4.14 2.58-5.42L6.17 5.17C4.23 6.82 3 9.26 3 12c0 4.97 4.03 9 9 9s9-4.03 9-9c0-2.74-1.23-5.18-3.17-6.83z"/></svg>
        {/if}
        <span class="source-label">{getSourceLabel(d.currentSource)}</span>
      </div>
      <div class="playback-controls">
        <button class="icon-btn" on:click={prev} aria-label="Precedent">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M6 6h2v12H6zm3.5 6l8.5 6V6z"/></svg>
        </button>
        <button class="icon-btn play" on:click={d.currentSource ? pause : play} aria-label="Play/Pause">
          {#if d.currentSource}
            <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>
          {:else}
            <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
          {/if}
        </button>
        <button class="icon-btn" on:click={next} aria-label="Suivant">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z"/></svg>
        </button>
        <button class="icon-btn" class:active={isMuted} on:click={toggleMute} aria-label="Mute">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            {#if isMuted}
              <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z"/>
            {:else}
              <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z"/>
            {/if}
          </svg>
        </button>
      </div>
    </div>

    {#if d.devices && d.devices.length > 1}
      <div class="stereo-section">
        <span class="section-label">Stereo</span>
        <div class="stereo-pair">
          {#each d.devices as dev}
            <div class="speaker-card" class:leader={dev.isLeader}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z"/></svg>
              <span class="speaker-role">{dev.role === 'FrontLeft' ? 'L' : 'R'}</span>
              <span class="speaker-name">{dev.name}</span>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    <div class="settings-row">
      <button class="night-btn" class:active={d.nightMode} on:click={toggleNight}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M9.37 5.51A7.35 7.35 0 0 0 9.1 7.5c0 4.08 3.32 7.4 7.4 7.4.68 0 1.35-.09 1.99-.27A7.014 7.014 0 0 1 12 19c-3.86 0-7-3.14-7-7 0-2.93 1.81-5.45 4.37-6.49z"/></svg>
        <span>Nuit</span>
      </button>
      <div class="eq-group">
        {#each eqPresets as preset}
          <button class="eq-btn" class:active={d.eqPreset === preset} on:click={() => setEq(preset)}>{eqLabels[preset]}</button>
        {/each}
      </div>
    </div>
  {/if}
</div>

<style>
  .devialet-page { width: 100%; height: 100%; display: flex; flex-direction: column; padding: 24px 28px; gap: 18px; overflow-y: auto; }

  /* Header */
  .header { display: flex; align-items: center; justify-content: space-between; }
  .header-left { display: flex; flex-direction: column; gap: 2px; }
  .system-name { font-size: 20px; font-weight: 700; color: #f0f0f0; margin: 0; }
  .model-info { font-size: 11px; color: #666; }
  .status-dot { width: 10px; height: 10px; border-radius: 50%; background: #ff4444; flex-shrink: 0; }
  .status-dot.online { background: #4caf50; }
  .offline-msg { flex: 1; display: flex; align-items: center; justify-content: center; color: #555; font-size: 14px; }

  /* Volume */
  .volume-section { display: flex; flex-direction: column; align-items: center; gap: 14px; padding: 12px 0; }
  .volume-circle { width: 120px; height: 120px; border-radius: 50%; border: 3px solid rgba(108, 99, 255, 0.4); display: flex; align-items: center; justify-content: center; gap: 2px; }
  .volume-number { font-size: 40px; font-weight: 700; color: #f0f0f0; font-variant-numeric: tabular-nums; }
  .volume-unit { font-size: 14px; color: #888; margin-top: 10px; }
  .volume-controls { display: flex; align-items: center; gap: 12px; width: 100%; max-width: 400px; }
  .vol-slider { -webkit-appearance: none; appearance: none; flex: 1; height: 6px; border-radius: 3px; background: rgba(255,255,255,0.1); outline: none; }
  .vol-slider::-webkit-slider-thumb { -webkit-appearance: none; width: 22px; height: 22px; border-radius: 50%; background: #6c63ff; cursor: pointer; }

  /* Shared icon button */
  .icon-btn { background: none; border: none; color: #888; padding: 10px; cursor: pointer; border-radius: 50%; display: flex; align-items: center; justify-content: center; min-width: 44px; min-height: 44px; -webkit-tap-highlight-color: transparent; transition: color 150ms; }
  .icon-btn:active { color: #f0f0f0; transform: scale(0.9); }
  .icon-btn.play { background: #6c63ff; color: #fff; min-width: 48px; min-height: 48px; }
  .icon-btn.play:active { opacity: 0.85; transform: scale(0.92); }
  .icon-btn.active { color: #6c63ff; }

  /* Source / Playback */
  .source-section { display: flex; align-items: center; justify-content: space-between; background: rgba(255,255,255,0.03); border-radius: 12px; padding: 14px 16px; }
  .source-info { display: flex; align-items: center; gap: 10px; }
  .source-icon { color: #6c63ff; flex-shrink: 0; }
  .source-icon.standby { color: #555; }
  .source-label { font-size: 14px; color: #ccc; font-weight: 500; }
  .playback-controls { display: flex; align-items: center; gap: 6px; }

  /* Stereo */
  .stereo-section { display: flex; flex-direction: column; gap: 8px; }
  .section-label { font-size: 10px; text-transform: uppercase; letter-spacing: 1.5px; color: #555; font-weight: 600; }
  .stereo-pair { display: flex; gap: 12px; }
  .speaker-card { flex: 1; display: flex; align-items: center; gap: 8px; background: rgba(255,255,255,0.03); border-radius: 10px; padding: 12px 14px; color: #888; border: 1px solid transparent; }
  .speaker-card.leader { border-color: rgba(108, 99, 255, 0.25); }
  .speaker-role { font-size: 13px; font-weight: 700; color: #6c63ff; min-width: 14px; }
  .speaker-name { font-size: 12px; color: #aaa; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; }

  /* Settings */
  .settings-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
  .night-btn { display: flex; align-items: center; gap: 6px; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); color: #888; font-size: 12px; font-weight: 500; padding: 10px 16px; border-radius: 10px; cursor: pointer; font-family: 'Inter', sans-serif; -webkit-tap-highlight-color: transparent; min-height: 44px; }
  .night-btn.active { color: #ffd54f; border-color: rgba(255, 213, 79, 0.3); }
  .night-btn:active { opacity: 0.7; }
  .eq-group { display: flex; gap: 4px; background: rgba(255,255,255,0.03); border-radius: 10px; padding: 4px; }
  .eq-btn { background: none; border: none; color: #666; font-size: 12px; font-weight: 500; padding: 8px 16px; border-radius: 8px; cursor: pointer; font-family: 'Inter', sans-serif; -webkit-tap-highlight-color: transparent; min-height: 44px; }
  .eq-btn.active { background: rgba(108, 99, 255, 0.2); color: #6c63ff; font-weight: 600; }
  .eq-btn:active { opacity: 0.7; }
</style>
