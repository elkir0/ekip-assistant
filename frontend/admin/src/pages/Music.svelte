<script>
  import { onMount } from 'svelte';
  import { apiGet, apiPut, showToast } from '../stores/auth.js';

  let config = {
    market: 'FR',
    search_limit: 10,
    queue_display_limit: 20,
    playlists_limit: 50,
    device_watch_attempts: 12,
    device_watch_interval_s: 5,
  };
  let loading = true;
  let saving = false;

  // Combined device watch preset: "attempts x interval"
  let deviceWatchPreset = 'normal';

  const deviceWatchPresets = {
    rapide:  { attempts: 10, interval: 30, label: 'Rapide (5 min)' },
    normal:  { attempts: 12, interval: 50, label: 'Normal (10 min)' },
    long:    { attempts: 20, interval: 60, label: 'Long (20 min)' },
  };

  function detectPreset() {
    const total = config.device_watch_attempts * config.device_watch_interval_s;
    if (total <= 300) return 'rapide';
    if (total <= 600) return 'normal';
    return 'long';
  }

  function applyDeviceWatchPreset() {
    const preset = deviceWatchPresets[deviceWatchPreset];
    if (preset) {
      config.device_watch_attempts = preset.attempts;
      config.device_watch_interval_s = preset.interval;
    }
  }

  onMount(async () => {
    const data = await apiGet('/admin/api/config');
    if (data && data.spotify) {
      config = { ...config, ...data.spotify };
    }
    deviceWatchPreset = detectPreset();
    loading = false;
  });

  async function save() {
    saving = true;
    const res = await apiPut('/admin/api/config/spotify', config);
    saving = false;
    if (res.ok) {
      showToast('Configuration Spotify sauvegardee', 'success');
    } else {
      showToast('Erreur lors de la sauvegarde', 'error');
    }
  }
</script>

<div class="page">
  <h1 class="page-title">Musique (Spotify)</h1>

  {#if loading}
    <div class="loading">Chargement...</div>
  {:else}
    <div class="card">
      <div class="form-group">
        <label class="form-label" for="market">Marche (code pays)</label>
        <select id="market" bind:value={config.market}>
          <option value="FR">FR - France</option>
          <option value="US">US - Etats-Unis</option>
          <option value="GB">GB - Royaume-Uni</option>
          <option value="DE">DE - Allemagne</option>
          <option value="ES">ES - Espagne</option>
          <option value="IT">IT - Italie</option>
          <option value="BR">BR - Bresil</option>
          <option value="JP">JP - Japon</option>
        </select>
      </div>

      <div class="form-group">
        <label class="form-label" for="search_limit">Limite recherche (resultats)</label>
        <select id="search_limit" bind:value={config.search_limit}>
          <option value={5}>5</option>
          <option value={10}>10</option>
          <option value={15}>15</option>
          <option value={20}>20</option>
          <option value={25}>25</option>
        </select>
      </div>

      <div class="form-group">
        <label class="form-label" for="queue_display_limit">Limite file d'attente (affichage)</label>
        <select id="queue_display_limit" bind:value={config.queue_display_limit}>
          <option value={5}>5</option>
          <option value={10}>10</option>
          <option value={15}>15</option>
          <option value={20}>20</option>
        </select>
      </div>

      <div class="form-group">
        <label class="form-label" for="playlists_limit">Limite playlists</label>
        <select id="playlists_limit" bind:value={config.playlists_limit}>
          <option value={10}>10</option>
          <option value={20}>20</option>
          <option value={50}>50</option>
          <option value={100}>100</option>
        </select>
      </div>

      <div class="form-group">
        <label class="form-label" for="device_watch">Detection du device Spotify</label>
        <select id="device_watch" bind:value={deviceWatchPreset} on:change={applyDeviceWatchPreset}>
          {#each Object.entries(deviceWatchPresets) as [key, preset]}
            <option value={key}>{preset.label}</option>
          {/each}
        </select>
        <div class="form-hint">
          {config.device_watch_attempts} tentatives toutes les {config.device_watch_interval_s}s
        </div>
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

  .form-hint {
    font-size: 11px;
    color: #666;
    margin-top: 4px;
  }

  select {
    background: #1a1a24;
    border: 1px solid #333;
    color: #f0f0f0;
    padding: 8px 12px;
    border-radius: 8px;
    font-size: 14px;
    width: 100%;
    font-family: 'Inter', sans-serif;
  }

  select:focus {
    border-color: #6c63ff;
    outline: none;
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
