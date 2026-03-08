<script>
  import { onMount } from 'svelte';
  import { apiGet, apiPut, showToast } from '../stores/auth.js';

  let config = {
    format: 'bestvideo[height<=480][vcodec^=avc]+bestaudio/best',
    search_limit: 8,
    search_timeout_s: 10,
    vlc_volume: 220,
    network_cache_ms: 1500,
    stop_timeout_s: 5,
  };
  let loading = true;
  let saving = false;

  const formatPresets = [
    { label: '360p', value: 'bestvideo[height<=360][vcodec^=avc]+bestaudio/best' },
    { label: '480p', value: 'bestvideo[height<=480][vcodec^=avc]+bestaudio/best' },
    { label: '720p', value: 'bestvideo[height<=720][vcodec^=avc]+bestaudio/best' },
  ];

  onMount(async () => {
    const data = await apiGet('/admin/api/config');
    if (data && data.youtube) {
      config = { ...config, ...data.youtube };
    }
    loading = false;
  });

  function applyPreset(preset) {
    config.format = preset.value;
  }

  async function save() {
    saving = true;
    const res = await apiPut('/admin/api/config/youtube', config);
    saving = false;
    if (res.ok) {
      showToast('Configuration YouTube sauvegardee', 'success');
    } else {
      showToast('Erreur lors de la sauvegarde', 'error');
    }
  }
</script>

<div class="page">
  <h1 class="page-title">YouTube</h1>

  {#if loading}
    <div class="loading">Chargement...</div>
  {:else}
    <div class="card">
      <div class="form-group">
        <label class="form-label" for="format">Format video</label>
        <input id="format" type="text" bind:value={config.format} />
        <div class="presets">
          {#each formatPresets as preset}
            <button class="preset-btn" on:click={() => applyPreset(preset)}>{preset.label}</button>
          {/each}
        </div>
      </div>

      <div class="form-group">
        <label class="form-label" for="search_limit">Limite resultats de recherche</label>
        <select id="search_limit" bind:value={config.search_limit}>
          <option value={3}>3</option>
          <option value={5}>5</option>
          <option value={8}>8</option>
          <option value={10}>10</option>
        </select>
      </div>

      <div class="form-group">
        <label class="form-label" for="search_timeout_s">Timeout recherche</label>
        <select id="search_timeout_s" bind:value={config.search_timeout_s}>
          <option value={10}>10 secondes</option>
          <option value={15}>15 secondes</option>
          <option value={20}>20 secondes</option>
          <option value={30}>30 secondes</option>
        </select>
      </div>

      <div class="form-group">
        <label class="form-label" for="vlc_volume">
          Volume VLC : {config.vlc_volume}
        </label>
        <input id="vlc_volume" type="range" bind:value={config.vlc_volume} min="0" max="512" step="10" />
        <div class="range-labels">
          <span>0</span>
          <span>512</span>
        </div>
      </div>

      <div class="form-group">
        <label class="form-label" for="network_cache_ms">Cache reseau</label>
        <select id="network_cache_ms" bind:value={config.network_cache_ms}>
          <option value={1000}>Faible latence (1000 ms)</option>
          <option value={3000}>Normal (3000 ms)</option>
          <option value={5000}>Stable (5000 ms)</option>
        </select>
      </div>

      <div class="form-group">
        <label class="form-label" for="stop_timeout_s">Timeout arret</label>
        <select id="stop_timeout_s" bind:value={config.stop_timeout_s}>
          <option value={3}>3 secondes</option>
          <option value={5}>5 secondes</option>
          <option value={10}>10 secondes</option>
        </select>
      </div>

      <button class="btn-save" on:click={save} disabled={saving}>
        {saving ? 'Sauvegarde...' : 'Sauvegarder'}
      </button>
    </div>
  {/if}
</div>

<style>
  .page { max-width: 600px; }

  .page-title {
    font-size: 22px;
    font-weight: 700;
    margin-bottom: 24px;
  }

  .loading {
    color: #888;
    padding: 40px;
    text-align: center;
  }

  .card {
    background: #111118;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    padding: 24px;
  }

  .form-group { margin-bottom: 20px; }

  .form-label {
    font-size: 13px;
    color: #888;
    margin-bottom: 6px;
    display: block;
  }

  input[type="text"], select {
    background: #1a1a24;
    border: 1px solid #333;
    color: #f0f0f0;
    padding: 8px 12px;
    border-radius: 8px;
    font-size: 14px;
    width: 100%;
    font-family: 'Inter', sans-serif;
  }

  input:focus, select:focus {
    border-color: #6c63ff;
    outline: none;
  }

  input[type="range"] {
    width: 100%;
    accent-color: #6c63ff;
  }

  .range-labels {
    display: flex;
    justify-content: space-between;
    font-size: 11px;
    color: #666;
    margin-top: 4px;
  }

  .presets {
    display: flex;
    gap: 8px;
    margin-top: 8px;
  }

  .preset-btn {
    background: #1a1a24;
    border: 1px solid #333;
    color: #888;
    padding: 4px 12px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 12px;
    font-family: 'Inter', sans-serif;
    transition: border-color 0.15s, color 0.15s;
  }

  .preset-btn:hover {
    border-color: #6c63ff;
    color: #6c63ff;
  }

  .btn-save {
    background: #6c63ff;
    color: white;
    border: none;
    padding: 10px 24px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 14px;
    font-family: 'Inter', sans-serif;
    font-weight: 500;
    transition: opacity 0.15s;
  }

  .btn-save:hover { opacity: 0.9; }
  .btn-save:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
