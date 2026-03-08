<script>
  import { onMount } from 'svelte';
  import { currentPage, assistantState, connectWS, wsConnected, fullscreenCam, transcript, speakingText } from './stores/assistant.js';
  import Music from './pages/Music.svelte';
  import Weather from './pages/Weather.svelte';
  import YouTube from './pages/YouTube.svelte';
  import Cameras from './pages/Cameras.svelte';
  import WaveAnimation from './components/WaveAnimation.svelte';

  const pages = [
    { name: 'Musique' },
    { name: 'Meteo' },
    { name: 'YouTube' },
    { name: 'Cameras' }
  ];

  let touchStartX = 0;
  let touchDeltaX = 0;
  let swiping = false;
  let dragOffset = 0;

  onMount(() => {
    connectWS();
  });

  function onTouchStart(e) {
    touchStartX = e.touches[0].clientX;
    swiping = true;
    touchDeltaX = 0;
    dragOffset = 0;
  }

  function onTouchMove(e) {
    if (!swiping) return;
    touchDeltaX = e.touches[0].clientX - touchStartX;
    const maxDrag = 80;
    dragOffset = Math.sign(touchDeltaX) * Math.min(Math.abs(touchDeltaX) * 0.3, maxDrag);
  }

  function onTouchEnd() {
    if (!swiping) return;
    swiping = false;

    if (Math.abs(touchDeltaX) > 60) {
      if (touchDeltaX < 0 && $currentPage < 3) {
        currentPage.set($currentPage + 1);
      } else if (touchDeltaX > 0 && $currentPage > 0) {
        currentPage.set($currentPage - 1);
      }
    }
    touchDeltaX = 0;
    dragOffset = 0;
  }

  // Clock
  let time = '';
  function updateClock() {
    const now = new Date();
    time = now.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
  }
  onMount(() => {
    updateClock();
    const interval = setInterval(updateClock, 10000);
    return () => clearInterval(interval);
  });
</script>

<div
  class="container"
  on:touchstart={onTouchStart}
  on:touchmove={onTouchMove}
  on:touchend={onTouchEnd}
>
  <div class="ambient-bg" class:listening={$assistantState === 'LISTENING'} class:speaking={$assistantState === 'SPEAKING'}></div>

  <header class="top-bar">
    <span class="clock">{time}</span>
    <span class="brand">pi-board</span>
    <span class="ws-dot" class:connected={$wsConnected}></span>
  </header>

  <div
    class="pages"
    class:dragging={swiping}
    style="transform: translateX(calc({-$currentPage * 100}vw + {dragOffset}px))"
  >
    <div class="page"><Music /></div>
    <div class="page"><Weather /></div>
    <div class="page"><YouTube /></div>
    <div class="page"><Cameras /></div>
  </div>

  <nav class="indicators">
    {#each pages as p, i}
      <button
        class="indicator"
        class:active={$currentPage === i}
        on:click={() => currentPage.set(i)}
        aria-label={p.name}
      >
        <span class="indicator-dot"></span>
        {#if $currentPage === i}
          <span class="indicator-label">{p.name}</span>
        {/if}
      </button>
    {/each}
  </nav>

  {#if $assistantState === 'LISTENING' || $assistantState === 'SPEAKING' || $assistantState === 'PROCESSING'}
    <div class="voice-pill">
      <WaveAnimation state={$assistantState} />
      <span class="voice-label">
        {#if $assistantState === 'LISTENING'}Ecoute...
        {:else if $assistantState === 'PROCESSING'}
          {#if $transcript}"{$transcript}"{:else}Reflexion...{/if}
        {:else}
          {#if $speakingText}{$speakingText}{:else}Parle...{/if}
        {/if}
      </span>
    </div>
  {/if}

  {#if $fullscreenCam}
    <button class="cam-fullscreen" on:click={() => fullscreenCam.set(null)}>
      <img src="/api/cameras/{$fullscreenCam.id}/stream" alt={$fullscreenCam.name} class="cam-fs-img" />
      <div class="cam-fs-bar">
        <span class="cam-fs-name">{$fullscreenCam.name}</span>
        <span class="cam-fs-hint">Appuyez pour fermer</span>
      </div>
    </button>
  {/if}
</div>

<style>
  .container {
    width: 100vw;
    height: 100vh;
    overflow: hidden;
    position: relative;
    background: #0a0a0f;
    touch-action: pan-x;
  }

  .ambient-bg {
    position: fixed;
    inset: 0;
    z-index: 0;
    opacity: 0.12;
    background: radial-gradient(ellipse 60% 40% at 50% 120%, #6c63ff, transparent);
    transition: opacity 800ms ease;
    pointer-events: none;
  }
  .ambient-bg.listening {
    opacity: 0.25;
    background: radial-gradient(ellipse 80% 50% at 50% 100%, #6c63ff, transparent);
  }
  .ambient-bg.speaking {
    opacity: 0.2;
    background: radial-gradient(ellipse 70% 45% at 50% 100%, #8b7fff, transparent);
  }

  .top-bar {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    z-index: 20;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 16px;
    background: linear-gradient(to bottom, rgba(10,10,15,0.95) 0%, transparent 100%);
  }

  .clock {
    font-size: 13px;
    font-weight: 500;
    color: #888;
  }

  .brand {
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 3px;
    text-transform: uppercase;
    color: #6c63ff;
    opacity: 0.7;
  }

  .ws-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #ff4444;
    transition: background 500ms ease;
  }
  .ws-dot.connected {
    background: #44ff88;
  }

  /* Horizontal swipe pages */
  .pages {
    position: relative;
    z-index: 1;
    display: flex;
    flex-direction: row;
    transition: transform 400ms cubic-bezier(0.22, 1, 0.36, 1);
    will-change: transform;
  }
  .pages.dragging {
    transition: none;
  }

  .page {
    width: 100vw;
    height: 100vh;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    position: relative;
  }

  /* Bottom horizontal dots */
  .indicators {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    display: flex;
    flex-direction: row;
    justify-content: center;
    gap: 4px;
    z-index: 20;
    align-items: center;
    padding: 6px 0 10px;
  }

  .indicator {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    background: none;
    border: none;
    cursor: pointer;
    padding: 14px 24px;
    -webkit-tap-highlight-color: transparent;
  }

  .indicator-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: rgba(255,255,255,0.2);
    transition: background 300ms ease, transform 300ms ease;
  }
  .indicator.active .indicator-dot {
    background: #6c63ff;
    transform: scale(1.3);
  }

  .indicator-label {
    font-size: 11px;
    color: #6c63ff;
    font-weight: 500;
    letter-spacing: 0.5px;
  }

  .voice-pill {
    position: fixed;
    top: 36px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 30;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    background: rgba(108, 99, 255, 0.15);
    border: 1px solid rgba(108, 99, 255, 0.3);
    border-radius: 20px;
    backdrop-filter: blur(8px);
    animation: pillIn 200ms ease-out;
  }

  .voice-label {
    font-size: 11px;
    font-weight: 500;
    color: #6c63ff;
    max-width: 500px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  @keyframes pillIn {
    from { transform: translateX(-50%) scale(0.8); opacity: 0; }
    to { transform: translateX(-50%) scale(1); opacity: 1; }
  }

  .cam-fullscreen {
    position: fixed;
    inset: 0;
    z-index: 100;
    background: #000;
    display: flex;
    align-items: center;
    justify-content: center;
    border: none;
    cursor: pointer;
    padding: 0;
    -webkit-tap-highlight-color: transparent;
  }
  .cam-fs-img {
    width: 100%;
    height: 100%;
    object-fit: contain;
  }
  .cam-fs-placeholder {
    color: #555;
    font-size: 16px;
  }
  .cam-fs-bar {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    padding: 12px 16px;
    background: linear-gradient(transparent, rgba(0,0,0,0.8));
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .cam-fs-name {
    font-size: 14px;
    font-weight: 500;
    color: #f0f0f0;
  }
  .cam-fs-hint {
    font-size: 11px;
    color: #555;
  }
</style>
