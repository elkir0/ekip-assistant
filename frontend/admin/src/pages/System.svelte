<script>
  import { onMount } from 'svelte';
  import { apiGet, apiPost, apiPut, showToast } from '../stores/auth.js';

  let system = null;
  let loading = true;
  let envContent = '';
  let envEntries = [];
  let savingEnv = false;
  let currentPassword = '';
  let newPassword = '';
  let confirmPassword = '';
  let savingPassword = false;
  let showRebootConfirm = false;
  let viewMode = 'structured'; // 'structured' or 'raw'
  let revealedKeys = {};

  const sensitivePatterns = ['KEY', 'SECRET', 'PASS', 'TOKEN', 'PASSWORD'];

  function isSensitive(key) {
    const upper = (key || '').toUpperCase();
    return sensitivePatterns.some(p => upper.includes(p));
  }

  function maskValue(value) {
    if (!value || value.length <= 4) return '****';
    return value.substring(0, 4) + '****';
  }

  function toggleReveal(key) {
    revealedKeys[key] = !revealedKeys[key];
    revealedKeys = revealedKeys;
  }

  function parseEnvEntries(content) {
    if (!content) return [];
    return content.split('\n').map((line, i) => {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#')) {
        return { type: 'comment', line, index: i };
      }
      const eqIdx = line.indexOf('=');
      if (eqIdx === -1) {
        return { type: 'comment', line, index: i };
      }
      return {
        type: 'entry',
        key: line.substring(0, eqIdx),
        value: line.substring(eqIdx + 1),
        index: i,
      };
    });
  }

  function entriesToContent() {
    return envEntries.map(e => {
      if (e.type === 'comment') return e.line;
      return `${e.key}=${e.value}`;
    }).join('\n');
  }

  onMount(async () => {
    const data = await apiGet('/admin/api/system');
    if (data) system = data;
    const envData = await apiGet('/admin/api/env');
    if (envData && envData.entries) {
      envContent = envData.entries.map(e => {
        if (e.type === 'comment') return e.line;
        return `${e.key}=${e.value}`;
      }).join('\n');
      envEntries = parseEnvEntries(envContent);
    }
    loading = false;
  });

  async function restartBackend() {
    const res = await apiPost('/admin/api/system/restart-backend', {});
    if (res.ok) {
      showToast('Backend en cours de redemarrage...', 'success');
    } else {
      showToast('Erreur lors du redemarrage', 'error');
    }
  }

  async function rebootPi() {
    showRebootConfirm = false;
    const res = await apiPost('/admin/api/system/reboot', {});
    if (res.ok) {
      showToast('Redemarrage du Pi en cours...', 'success');
    } else {
      showToast('Erreur lors du redemarrage', 'error');
    }
  }

  async function saveEnv() {
    savingEnv = true;
    // Sync views
    if (viewMode === 'raw') {
      envEntries = parseEnvEntries(envContent);
    } else {
      envContent = entriesToContent();
    }
    // Backend expects { entries: [{key, value}, ...] }
    const payload = envEntries
      .filter(e => e.type === 'entry')
      .map(e => ({ key: e.key, value: e.value }));
    const res = await apiPut('/admin/api/env', { entries: payload });
    savingEnv = false;
    if (res.ok) {
      showToast('Fichier .env sauvegarde', 'success');
    } else {
      showToast('Erreur lors de la sauvegarde', 'error');
    }
  }

  function switchViewMode(mode) {
    if (mode === viewMode) return;
    if (mode === 'raw') {
      envContent = entriesToContent();
    } else {
      envEntries = parseEnvEntries(envContent);
    }
    viewMode = mode;
  }

  async function changePassword() {
    if (!currentPassword) {
      showToast('Veuillez entrer le mot de passe actuel', 'error');
      return;
    }
    if (!newPassword || newPassword.length < 4) {
      showToast('Le mot de passe doit faire au moins 4 caracteres', 'error');
      return;
    }
    if (newPassword !== confirmPassword) {
      showToast('Les mots de passe ne correspondent pas', 'error');
      return;
    }
    savingPassword = true;
    const res = await apiPost('/admin/api/password', { current: currentPassword, new: newPassword });
    savingPassword = false;
    if (res.ok) {
      showToast('Mot de passe modifie', 'success');
      currentPassword = '';
      newPassword = '';
      confirmPassword = '';
    } else {
      showToast('Erreur lors du changement', 'error');
    }
  }

  function formatUptime(seconds) {
    if (!seconds) return '-';
    const d = Math.floor(seconds / 86400);
    const h = Math.floor((seconds % 86400) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    if (d > 0) return `${d}j ${h}h ${m}m`;
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
  }
</script>

<div class="page">
  <h1 class="page-title">Systeme</h1>

  {#if loading}
    <div class="loading">Chargement...</div>
  {:else}
    <!-- System Info -->
    <div class="card">
      <h2 class="section-title">Informations systeme</h2>
      {#if system}
        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">Hostname</span>
            <span class="info-value">{system.hostname || '-'}</span>
          </div>
          <div class="info-item">
            <span class="info-label">IP</span>
            <span class="info-value">{system.ip || '-'}</span>
          </div>
          <div class="info-item">
            <span class="info-label">CPU Temp</span>
            <span class="info-value">{system.cpu_temp != null ? `${system.cpu_temp.toFixed(1)} C` : '-'}</span>
          </div>
          <div class="info-item">
            <span class="info-label">RAM</span>
            <span class="info-value">{system.memory?.percent != null ? `${system.memory.percent.toFixed(0)}%` : '-'} ({system.memory?.used_mb || '-'} / {system.memory?.total_mb || '-'} MB)</span>
          </div>
          <div class="info-item">
            <span class="info-label">Disque</span>
            <span class="info-value">{system.disk?.percent != null ? `${system.disk.percent.toFixed(0)}%` : '-'} ({system.disk?.used_gb || '-'} / {system.disk?.total_gb || '-'} GB)</span>
          </div>
          <div class="info-item">
            <span class="info-label">Uptime</span>
            <span class="info-value">{formatUptime(system.uptime?.seconds)}</span>
          </div>
          <div class="info-item">
            <span class="info-label">Python</span>
            <span class="info-value">{system.python_version || '-'}</span>
          </div>
          <div class="info-item">
            <span class="info-label">OS</span>
            <span class="info-value">{system.os_version || '-'}</span>
          </div>
        </div>
      {:else}
        <p style="color: #888;">Informations non disponibles.</p>
      {/if}
    </div>

    <!-- Actions -->
    <div class="card">
      <h2 class="section-title">Actions</h2>
      <div class="actions-row">
        <button class="btn-action" on:click={restartBackend}>
          Redemarrer le backend
        </button>
        <button class="btn-action btn-danger" on:click={() => showRebootConfirm = true}>
          Redemarrer le Pi
        </button>
      </div>

      {#if showRebootConfirm}
        <div class="confirm-box">
          <p>Etes-vous sur de vouloir redemarrer le Raspberry Pi ?</p>
          <div class="confirm-actions">
            <button class="btn-action btn-danger" on:click={rebootPi}>Confirmer</button>
            <button class="btn-action" on:click={() => showRebootConfirm = false}>Annuler</button>
          </div>
        </div>
      {/if}
    </div>

    <!-- Env Editor -->
    <div class="card">
      <div class="env-header">
        <h2 class="section-title" style="margin-bottom: 0;">Variables d'environnement (.env)</h2>
        <div class="view-toggle">
          <button class="toggle-btn" class:active={viewMode === 'structured'} on:click={() => switchViewMode('structured')}>
            Structure
          </button>
          <button class="toggle-btn" class:active={viewMode === 'raw'} on:click={() => switchViewMode('raw')}>
            Brut
          </button>
        </div>
      </div>

      {#if viewMode === 'structured'}
        <div class="env-structured">
          {#each envEntries as entry, i}
            {#if entry.type === 'comment'}
              {#if entry.line.trim().startsWith('#') && entry.line.trim().length > 1}
                <div class="env-comment">{entry.line}</div>
              {/if}
            {:else}
              <div class="env-row">
                <div class="env-key">{entry.key}</div>
                <div class="env-value-row">
                  {#if isSensitive(entry.key) && !revealedKeys[entry.key]}
                    <input
                      type="password"
                      class="env-input"
                      bind:value={envEntries[i].value}
                      placeholder="(vide)"
                    />
                  {:else}
                    <input
                      type="text"
                      class="env-input"
                      bind:value={envEntries[i].value}
                      placeholder="(vide)"
                    />
                  {/if}
                  {#if isSensitive(entry.key)}
                    <button class="eye-btn" on:click={() => toggleReveal(entry.key)} title={revealedKeys[entry.key] ? 'Masquer' : 'Afficher'}>
                      {#if revealedKeys[entry.key]}
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                          <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24" />
                          <line x1="1" y1="1" x2="23" y2="23" />
                        </svg>
                      {:else}
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                          <circle cx="12" cy="12" r="3" />
                        </svg>
                      {/if}
                    </button>
                  {/if}
                </div>
              </div>
            {/if}
          {/each}
        </div>
      {:else}
        <div class="form-group">
          <textarea class="env-editor" bind:value={envContent} rows="15" spellcheck="false"></textarea>
        </div>
      {/if}

      <button class="btn-save" on:click={saveEnv} disabled={savingEnv}>
        {savingEnv ? 'Sauvegarde...' : 'Sauvegarder .env'}
      </button>
    </div>

    <!-- Password Change -->
    <div class="card">
      <h2 class="section-title">Changer le mot de passe</h2>
      <div class="form-group">
        <label class="form-label" for="current_password">Mot de passe actuel</label>
        <input id="current_password" type="password" bind:value={currentPassword} placeholder="Mot de passe actuel" />
      </div>
      <div class="form-group">
        <label class="form-label" for="new_password">Nouveau mot de passe</label>
        <input id="new_password" type="password" bind:value={newPassword} placeholder="Minimum 4 caracteres" />
      </div>
      <div class="form-group">
        <label class="form-label" for="confirm_password">Confirmer le mot de passe</label>
        <input id="confirm_password" type="password" bind:value={confirmPassword} placeholder="Retapez le mot de passe" />
      </div>
      <button class="btn-save" on:click={changePassword} disabled={savingPassword}>
        {savingPassword ? 'Modification...' : 'Modifier le mot de passe'}
      </button>
    </div>
  {/if}
</div>

<style>
  .page { max-width: 700px; }

  .page-title {
    font-size: 22px;
    font-weight: 700;
    margin-bottom: 24px;
  }

  .section-title {
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 20px;
    color: #ccc;
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
    margin-bottom: 16px;
  }

  .info-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }

  .info-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .info-label {
    font-size: 11px;
    color: #666;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .info-value {
    font-size: 14px;
    color: #f0f0f0;
    font-family: 'JetBrains Mono', monospace;
  }

  .actions-row {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
  }

  .btn-action {
    background: #1a1a24;
    border: 1px solid #333;
    color: #f0f0f0;
    padding: 10px 20px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 13px;
    font-family: 'Inter', sans-serif;
    font-weight: 500;
    transition: border-color 0.15s;
  }

  .btn-action:hover {
    border-color: #6c63ff;
  }

  .btn-danger {
    border-color: rgba(255, 107, 107, 0.3);
    color: #ff6b6b;
  }

  .btn-danger:hover {
    border-color: #ff6b6b;
  }

  .confirm-box {
    margin-top: 16px;
    padding: 16px;
    background: rgba(255, 107, 107, 0.08);
    border: 1px solid rgba(255, 107, 107, 0.2);
    border-radius: 8px;
  }

  .confirm-box p {
    margin-bottom: 12px;
    font-size: 14px;
    color: #ff6b6b;
  }

  .confirm-actions {
    display: flex;
    gap: 8px;
  }

  /* Env editor */
  .env-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
    flex-wrap: wrap;
    gap: 8px;
  }

  .view-toggle {
    display: flex;
    gap: 2px;
    background: #0a0a0f;
    border-radius: 6px;
    padding: 2px;
  }

  .toggle-btn {
    background: none;
    border: none;
    color: #666;
    padding: 5px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-family: 'Inter', sans-serif;
    transition: background 0.15s, color 0.15s;
  }

  .toggle-btn.active {
    background: #1a1a24;
    color: #f0f0f0;
  }

  .toggle-btn:hover:not(.active) {
    color: #888;
  }

  .env-structured {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-bottom: 16px;
    max-height: 500px;
    overflow-y: auto;
  }

  .env-comment {
    font-size: 12px;
    color: #555;
    font-family: 'JetBrains Mono', monospace;
    padding: 4px 0;
    margin-top: 8px;
  }

  .env-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 0;
  }

  .env-key {
    font-size: 12px;
    color: #6c63ff;
    font-family: 'JetBrains Mono', monospace;
    min-width: 200px;
    flex-shrink: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .env-value-row {
    display: flex;
    align-items: center;
    gap: 4px;
    flex: 1;
    min-width: 0;
  }

  .env-input {
    background: #0a0a0f;
    border: 1px solid #333;
    color: #f0f0f0;
    padding: 5px 8px;
    border-radius: 4px;
    font-size: 12px;
    font-family: 'JetBrains Mono', monospace;
    width: 100%;
    min-width: 0;
  }

  .env-input:focus {
    border-color: #6c63ff;
    outline: none;
  }

  .eye-btn {
    background: none;
    border: 1px solid #333;
    border-radius: 4px;
    color: #666;
    cursor: pointer;
    padding: 4px 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: color 0.15s, border-color 0.15s;
  }

  .eye-btn:hover {
    color: #f0f0f0;
    border-color: #6c63ff;
  }

  .form-group { margin-bottom: 20px; }

  .form-label {
    font-size: 13px;
    color: #888;
    margin-bottom: 6px;
    display: block;
  }

  input[type="password"] {
    background: #1a1a24;
    border: 1px solid #333;
    color: #f0f0f0;
    padding: 8px 12px;
    border-radius: 8px;
    font-size: 14px;
    width: 100%;
    font-family: 'Inter', sans-serif;
  }

  input:focus {
    border-color: #6c63ff;
    outline: none;
  }

  .env-editor {
    background: #0a0a0f;
    border: 1px solid #333;
    color: #f0f0f0;
    padding: 12px;
    border-radius: 8px;
    font-size: 13px;
    width: 100%;
    font-family: 'JetBrains Mono', monospace;
    resize: vertical;
    min-height: 200px;
    line-height: 1.6;
  }

  .env-editor:focus {
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

  @media (max-width: 768px) {
    .info-grid {
      grid-template-columns: 1fr;
    }

    .env-row {
      flex-direction: column;
      align-items: flex-start;
      gap: 4px;
    }

    .env-key {
      min-width: 0;
    }

    .env-value-row {
      width: 100%;
    }
  }
</style>
