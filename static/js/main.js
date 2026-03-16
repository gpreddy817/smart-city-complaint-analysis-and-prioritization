/* static/js/main.js - GPS capture, emergency alerts, UI enhancements */

// ── GPS Capture ───────────────────────────────────────────────────────────────

function initGPS() {
  const statusEl = document.getElementById('gps-status');
  const latInput = document.getElementById('latitude');
  const lngInput = document.getElementById('longitude');
  if (!statusEl || !latInput) return;

  if (!navigator.geolocation) {
    statusEl.textContent = '📍 GPS not supported by browser';
    statusEl.className = 'gps-status error';
    return;
  }

  statusEl.textContent = '⏳ Requesting GPS location...';
  statusEl.className = 'gps-status pending';

  navigator.geolocation.getCurrentPosition(
    function (pos) {
      const lat = pos.coords.latitude.toFixed(6);
      const lng = pos.coords.longitude.toFixed(6);
      latInput.value = lat;
      lngInput.value = lng;
      statusEl.innerHTML = `✅ GPS Captured: ${lat}, ${lng}`;
      statusEl.className = 'gps-status success';
    },
    function (err) {
      let msg = '❌ GPS unavailable';
      if (err.code === 1) msg = '❌ GPS permission denied - enter location manually';
      else if (err.code === 2) msg = '❌ GPS position unavailable';
      statusEl.textContent = msg;
      statusEl.className = 'gps-status error';
    },
    { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
  );
}

// ── Emergency Alert Sound ─────────────────────────────────────────────────────

function playAlertSound() {
  try {
    // Create beeping sound using Web Audio API (no external file needed)
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    function beep(freq, start, dur) {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.frequency.value = freq;
      osc.type = 'square';
      gain.gain.setValueAtTime(0.3, ctx.currentTime + start);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + start + dur);
      osc.start(ctx.currentTime + start);
      osc.stop(ctx.currentTime + start + dur);
    }
    // Pattern: 3 quick beeps
    beep(880, 0, 0.2);
    beep(880, 0.3, 0.2);
    beep(1100, 0.6, 0.4);
  } catch (e) {
    console.warn('Audio not available:', e);
  }
}

function checkEmergency() {
  const banner = document.getElementById('emergency-banner');
  if (banner) {
    // Play sound on first load if emergency active
    playAlertSound();
    // Repeat every 8 seconds
    setInterval(playAlertSound, 8000);
  }
}

// ── Flash Message Auto-dismiss ────────────────────────────────────────────────

function initAlerts() {
  setTimeout(() => {
    document.querySelectorAll('.alert-dismissible').forEach(el => {
      el.style.transition = 'opacity 1s';
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 1000);
    });
  }, 5000);
}

// ── Complaint Text Preview ────────────────────────────────────────────────────

function initTextCounter() {
  const textarea = document.getElementById('complaint_text');
  const counter = document.getElementById('char-counter');
  if (!textarea || !counter) return;
  textarea.addEventListener('input', () => {
    const len = textarea.value.length;
    counter.textContent = `${len} characters`;
    counter.style.color = len < 20 ? '#dc3545' : '#28a745';
  });
}

// ── Dashboard Polling (check for new emergencies every 30s) ──────────────────

function pollEmergencies() {
  if (!document.getElementById('dashboard-page')) return;
  setInterval(() => {
    fetch('/api/emergency-status')
      .then(r => r.json())
      .then(data => {
        const banner = document.getElementById('emergency-banner');
        if (data.active_emergencies > 0 && !banner) {
          location.reload(); // reload to show banner
        }
      })
      .catch(() => {});
  }, 30000);
}

// ── Initialize ────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {
  initGPS();
  checkEmergency();
  initAlerts();
  initTextCounter();
  pollEmergencies();
});
