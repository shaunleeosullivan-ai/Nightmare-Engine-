/* ═══════════════════════════════════════════════════════════════
   ANIMATED STORYBOOK NARRATOR — Client Application
   ═══════════════════════════════════════════════════════════════ */

'use strict';

// ── Utility ───────────────────────────────────────────────────────────────────

function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function typographyFix(text) {
  return text
    .replace(/--/g, '\u2014')                          // em dash
    .replace(/(\w)'(\w)/g, '$1\u2019$2')               // apostrophe
    .replace(/"([^"]*)"/g, '\u201c$1\u201d')           // "smart quotes"
    .replace(/'([^']*)'/g, '\u2018$1\u2019');          // 'smart quotes'
}

function delay(ms) {
  return new Promise(r => setTimeout(r, ms));
}

// ── Particle System ───────────────────────────────────────────────────────────

class ParticleSystem {
  constructor() {
    this.canvas = document.getElementById('particles');
    this.ctx    = this.canvas.getContext('2d');
    this.parts  = [];
    this.resize();
    window.addEventListener('resize', () => this.resize());
    for (let i = 0; i < 55; i++) this.parts.push(this.newParticle(true));
    this.loop();
  }

  resize() {
    this.canvas.width  = window.innerWidth;
    this.canvas.height = window.innerHeight;
  }

  newParticle(randomY = false) {
    return {
      x:       Math.random() * this.canvas.width,
      y:       randomY ? Math.random() * this.canvas.height : this.canvas.height + 4,
      r:       Math.random() * 1.4 + 0.3,
      opacity: Math.random() * 0.30 + 0.05,
      vx:      (Math.random() - 0.5) * 0.35,
      vy:      -(Math.random() * 0.38 + 0.08),
      wobble:  Math.random() * Math.PI * 2,
      ws:      (Math.random() - 0.5) * 0.018,
    };
  }

  loop() {
    const { ctx, canvas, parts } = this;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (let i = 0; i < parts.length; i++) {
      const p = parts[i];
      p.wobble += p.ws;
      p.x += p.vx + Math.sin(p.wobble) * 0.25;
      p.y += p.vy;
      if (p.y < -4 || p.x < -4 || p.x > canvas.width + 4) parts[i] = this.newParticle();
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(255,205,110,${p.opacity})`;
      ctx.fill();
    }
    requestAnimationFrame(() => this.loop());
  }
}

// ── Page Turn Sound (synthesised) ─────────────────────────────────────────────

function playPageTurnSound() {
  try {
    const ctx    = new (window.AudioContext || window.webkitAudioContext)();
    const sr     = ctx.sampleRate;
    const dur    = 0.32;
    const buf    = ctx.createBuffer(1, sr * dur, sr);
    const data   = buf.getChannelData(0);

    for (let i = 0; i < data.length; i++) {
      const t = i / sr;
      // Whooshing paper noise with slight flutter
      data[i] = (Math.random() * 2 - 1) *
                Math.exp(-8 * t) *                       // fast decay
                (0.7 + 0.3 * Math.sin(t * 40));          // subtle flutter
    }

    const src = ctx.createBufferSource();
    src.buffer = buf;

    const bp = ctx.createBiquadFilter();
    bp.type = 'bandpass';
    bp.frequency.value = 2800;
    bp.Q.value = 0.7;

    const gain = ctx.createGain();
    gain.gain.setValueAtTime(0.18, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + dur);

    src.connect(bp).connect ? src.connect(bp) : undefined;
    bp.connect(gain);
    gain.connect(ctx.destination);
    src.connect(bp);
    src.start();

    setTimeout(() => ctx.close(), 1000);
  } catch (_) { /* Audio not available — continue silently */ }
}

// ── StoryBook Application ─────────────────────────────────────────────────────

class StoryBook {
  constructor() {
    this.pages         = [];
    this.currentSpread = 0;
    this.totalSpreads  = 0;
    this.bookTitle     = 'Your Story';

    this.isPaused      = false;
    this.isAnimating   = false;
    this.isSpeaking    = false;
    this.isFinished    = false;

    this.speechRate    = 0.9;
    this.speechVolume  = 1.0;
    this.voices        = [];
    this.narratorVoice = null;

    // How many page turns between AI commentary
    this.commentaryEvery       = 2;
    this.turnsSinceCommentary  = 0;

    // Pause-aware continuation
    this._resumeResolve = null;

    // DOM
    this.$ = id => document.getElementById(id);

    this.initDOM();
    this.loadVoices().then(() => this.setup());
  }

  initDOM() {
    this.dom = {
      uploadOverlay:    this.$('upload-overlay'),
      uploadZone:       this.$('upload-zone'),
      fileInput:        this.$('file-input'),
      textInput:        this.$('text-input'),
      charCount:        this.$('char-count'),
      startBtn:         this.$('start-btn'),
      startHint:        this.$('start-hint'),
      bookClosed:       this.$('book-closed'),
      bookSpread:       this.$('book-spread'),
      coverTitleText:   this.$('cover-title-text'),
      leftContent:      this.$('left-content'),
      rightContent:     this.$('right-content'),
      flipWrapper:      this.$('flip-wrapper'),
      flipFront:        this.$('flip-front-content'),
      flipBack:         this.$('flip-back-content'),
      controlsBar:      this.$('controls-bar'),
      pauseBtn:         this.$('pause-btn'),
      pauseIcon:        this.$('pause-icon'),
      pauseLabel:       this.$('pause-label'),
      speedSlider:      this.$('speed-slider'),
      speedLabel:       this.$('speed-label'),
      volumeSlider:     this.$('volume-slider'),
      progressFill:     this.$('progress-fill'),
      pageIndicator:    this.$('page-indicator'),
      narratorBubble:   this.$('narrator-bubble'),
      bubbleText:       this.$('bubble-text'),
      narratorIndicator: this.$('narrator-indicator'),
    };
  }

  // ── Voice Loading ───────────────────────────────────────────────────────────

  async loadVoices() {
    return new Promise(resolve => {
      const tryLoad = () => {
        const v = speechSynthesis.getVoices();
        if (!v.length) return;
        this.voices = v;
        // Preference order for warm narrator voices
        this.narratorVoice =
          v.find(x => x.name === 'Google UK English Female') ||
          v.find(x => x.name === 'Samantha') ||
          v.find(x => x.name === 'Karen')    ||
          v.find(x => x.name === 'Moira')    ||
          v.find(x => x.name === 'Serena')   ||
          v.find(x => x.lang === 'en-GB' && /female/i.test(x.name)) ||
          v.find(x => x.lang.startsWith('en') && !/male/i.test(x.name)) ||
          v.find(x => x.lang.startsWith('en')) ||
          v[0] || null;
        resolve();
      };
      speechSynthesis.addEventListener('voiceschanged', tryLoad);
      tryLoad();
      setTimeout(resolve, 2500); // Fallback timeout
    });
  }

  // ── Event Setup ─────────────────────────────────────────────────────────────

  setup() {
    const { dom } = this;

    // Text area — live feedback
    dom.textInput.addEventListener('input', () => {
      const len = dom.textInput.value.length;
      dom.charCount.textContent = len.toLocaleString() + ' character' + (len !== 1 ? 's' : '');
      const hasText = len > 20;
      dom.startBtn.disabled = !hasText;
      dom.startHint.textContent = hasText ? 'Ready — click to begin!' : 'Add some text above to begin';
    });

    // File drag & drop
    dom.uploadZone.addEventListener('dragover', e => {
      e.preventDefault();
      dom.uploadZone.classList.add('dragover');
    });
    dom.uploadZone.addEventListener('dragleave', () =>
      dom.uploadZone.classList.remove('dragover'));
    dom.uploadZone.addEventListener('drop', e => {
      e.preventDefault();
      dom.uploadZone.classList.remove('dragover');
      const file = e.dataTransfer.files[0];
      if (file) this.readFile(file);
    });

    // File picker
    dom.fileInput.addEventListener('change', e => {
      const file = e.target.files[0];
      if (file) this.readFile(file);
    });

    // Start
    dom.startBtn.addEventListener('click', () => {
      const text = dom.textInput.value.trim();
      if (text.length > 20) this.startStory(text, dom.textInput.dataset.filename || 'Your Story');
    });

    // Pause / Resume
    dom.pauseBtn.addEventListener('click', () => this.togglePause());

    // Speed
    dom.speedSlider.addEventListener('input', e => {
      this.speechRate = parseFloat(e.target.value);
      dom.speedLabel.textContent = this.speechRate.toFixed(1) + '×';
      if (speechSynthesis.speaking) {
        // Apply immediately by restarting current utterance (rate changes on next speak)
      }
    });

    // Volume
    dom.volumeSlider.addEventListener('input', e => {
      this.speechVolume = parseFloat(e.target.value);
    });
  }

  readFile(file) {
    const reader = new FileReader();
    reader.onload = e => {
      const text = e.target.result;
      this.dom.textInput.value = text;
      this.dom.textInput.dataset.filename = file.name;
      // Extract title from filename
      const title = file.name.replace(/\.[^.]+$/, '').replace(/[-_]/g, ' ');
      this.dom.coverTitleText.textContent = title;
      this.bookTitle = title;
      // Trigger input event for char count + button enable
      this.dom.textInput.dispatchEvent(new Event('input'));
    };
    reader.readAsText(file, 'UTF-8');
  }

  // ── Text Pagination ─────────────────────────────────────────────────────────

  paginateText(rawText) {
    const MAX_CHARS = 860;

    // Split into paragraphs, clean whitespace
    const paragraphs = rawText
      .replace(/\r\n/g, '\n')
      .split(/\n{2,}/)
      .map(p => p.replace(/\n/g, ' ').replace(/\s+/g, ' ').trim())
      .filter(Boolean);

    const pages = [];
    let current = [];
    let currentLen = 0;

    for (const para of paragraphs) {
      const cost = para.length + (current.length ? 2 : 0);
      if (currentLen + cost > MAX_CHARS && current.length) {
        pages.push(current.join('\n\n'));
        current = [para];
        currentLen = para.length;
      } else {
        current.push(para);
        currentLen += cost;
      }
    }

    if (current.length) pages.push(current.join('\n\n'));
    return pages;
  }

  // ── HTML Rendering ──────────────────────────────────────────────────────────

  formatPageHTML(text, pageIndex, side = 'left') {
    const paras = text.split('\n\n').filter(Boolean);
    let html = '<div class="page-content-inner">';

    paras.forEach((raw, i) => {
      const para = typographyFix(escapeHtml(raw));
      // Detect chapter heading (short ALL-CAPS line or "Chapter N" pattern)
      if (/^(chapter\s+\w+|part\s+\w+|prologue|epilogue)/i.test(raw.trim()) && raw.trim().length < 60) {
        html += `<p class="chapter-heading">${para}</p>`;
        return;
      }
      // Drop cap on very first paragraph of the whole story
      if (i === 0 && pageIndex === 0) {
        const cap  = para[0];
        const rest = para.slice(1);
        html += `<p class="para drop-cap"><span class="cap">${cap}</span>${rest}</p>`;
      } else {
        html += `<p class="para">${para}</p>`;
      }
    });

    html += '</div>';
    html += `<div class="page-number">${pageIndex + 1}</div>`;
    return html;
  }

  endPageHTML() {
    return `
      <div class="page-content-inner page-end">
        <p class="end-ornament">✦ &nbsp; ✦ &nbsp; ✦</p>
        <p class="end-text">The End</p>
        <p class="end-ornament">✦</p>
      </div>`;
  }

  blankPageHTML() {
    return '<div class="page-content-inner"></div>';
  }

  // ── Spread Index Helpers ────────────────────────────────────────────────────

  /*
   * Spread layout:
   *   Spread 0: left = blank,         right = pages[0]
   *   Spread 1: left = pages[1],      right = pages[2]
   *   Spread k: left = pages[2k-1],   right = pages[2k]
   */
  getSpreadIndices(spread) {
    return {
      left:  spread === 0 ? -1 : spread * 2 - 1,
      right: spread * 2,
    };
  }

  // ── Book Startup ────────────────────────────────────────────────────────────

  async startStory(rawText, filename = 'Your Story') {
    this.pages        = this.paginateText(rawText);
    this.totalSpreads = Math.ceil((this.pages.length + 1) / 2);
    this.currentSpread = 0;
    this.bookTitle     = filename !== 'Your Story' ? filename : this.detectTitle(rawText);

    if (this.dom.coverTitleText.textContent === 'Your Story') {
      this.dom.coverTitleText.textContent = this.bookTitle;
    }

    // Fade out upload overlay
    this.dom.uploadOverlay.classList.add('hidden');
    await delay(700);

    // Show book, animate opening
    await this.openBook();

    // Show controls
    this.dom.controlsBar.classList.add('visible');

    // Load first spread
    this.loadSpread(0);

    // Brief pause, then narrate
    await delay(900);
    this.narrateCurrentSpread();
  }

  detectTitle(text) {
    // Try to find a title from the first non-empty short line
    const firstLine = text.split('\n').find(l => l.trim().length > 0);
    if (firstLine && firstLine.trim().length < 70) return firstLine.trim();
    return 'Your Story';
  }

  async openBook() {
    const { bookClosed, bookSpread } = this.dom;

    // Animate cover away
    bookClosed.style.transition = 'opacity 0.65s ease, transform 0.65s ease';
    bookClosed.style.opacity    = '0';
    bookClosed.style.transform  = 'scale(0.92) rotateY(-12deg)';
    await delay(650);
    bookClosed.style.display = 'none';

    // Reveal open book
    bookSpread.classList.add('open');
    bookSpread.classList.add('appearing');
    await delay(950);
    bookSpread.classList.remove('appearing');
  }

  // ── Spread Loading ──────────────────────────────────────────────────────────

  loadSpread(spreadIndex) {
    const { left, right } = this.getSpreadIndices(spreadIndex);

    // Left page
    if (left < 0 || left >= this.pages.length) {
      this.dom.leftContent.innerHTML = this.blankPageHTML();
    } else {
      this.dom.leftContent.innerHTML = this.formatPageHTML(this.pages[left], left, 'left');
      this.dom.leftContent.classList.add('refreshing');
      setTimeout(() => this.dom.leftContent.classList.remove('refreshing'), 450);
    }

    // Right page
    if (right >= this.pages.length) {
      this.dom.rightContent.innerHTML = this.endPageHTML();
    } else {
      this.dom.rightContent.innerHTML = this.formatPageHTML(this.pages[right], right, 'right');
      this.dom.rightContent.classList.add('refreshing');
      setTimeout(() => this.dom.rightContent.classList.remove('refreshing'), 450);
    }

    this.updateProgress(spreadIndex);
  }

  // ── Page Turn ───────────────────────────────────────────────────────────────

  async turnPage() {
    if (this.isAnimating) return;
    this.isAnimating = true;

    const next = this.currentSpread + 1;
    const { left: nextLeft, right: nextRight } = this.getSpreadIndices(next);
    const { right: currRight } = this.getSpreadIndices(this.currentSpread);

    // --- Prepare flip faces ---
    // Front face = current right page (what we "lift")
    if (currRight < this.pages.length) {
      this.dom.flipFront.innerHTML = this.formatPageHTML(this.pages[currRight], currRight, 'right');
    } else {
      this.dom.flipFront.innerHTML = this.endPageHTML();
    }

    // Back face = next spread's left page (revealed after flip)
    if (nextLeft >= 0 && nextLeft < this.pages.length) {
      this.dom.flipBack.innerHTML = this.formatPageHTML(this.pages[nextLeft], nextLeft, 'left');
    } else {
      this.dom.flipBack.innerHTML = this.blankPageHTML();
    }

    // --- Update underlying pages to next spread content (hidden during flip) ---
    if (nextLeft < 0 || nextLeft >= this.pages.length) {
      this.dom.leftContent.innerHTML = this.blankPageHTML();
    } else {
      this.dom.leftContent.innerHTML = this.formatPageHTML(this.pages[nextLeft], nextLeft, 'left');
    }
    if (nextRight >= this.pages.length) {
      this.dom.rightContent.innerHTML = this.endPageHTML();
    } else {
      this.dom.rightContent.innerHTML = this.formatPageHTML(this.pages[nextRight], nextRight, 'right');
    }

    // --- Run animation ---
    playPageTurnSound();

    this.dom.flipWrapper.style.display = 'block';
    this.dom.flipWrapper.offsetHeight; // force reflow
    this.dom.flipWrapper.classList.add('flipping');

    await delay(1700); // match animation duration + small buffer

    this.dom.flipWrapper.classList.remove('flipping');
    this.dom.flipWrapper.style.display = 'none';

    this.isAnimating = false;
  }

  // ── Narration Flow ──────────────────────────────────────────────────────────

  async narrateCurrentSpread() {
    if (this.isFinished || this.isPaused) {
      if (this.isPaused) {
        // Will be resumed by togglePause
        this._pendingResume = true;
      }
      return;
    }

    const { left, right } = this.getSpreadIndices(this.currentSpread);

    // Read left page
    if (left >= 0 && left < this.pages.length) {
      await this.speak(this.pages[left]);
      if (this.isPaused) { this._pendingResume = true; return; }
      await this.pauseAware(500);
    }

    // Read right page
    if (right < this.pages.length) {
      await this.speak(this.pages[right]);
      if (this.isPaused) { this._pendingResume = true; return; }
      await this.pauseAware(700);
    }

    // Collect context for commentary
    const chunkParts = [];
    if (left >= 0 && left < this.pages.length)   chunkParts.push(this.pages[left]);
    if (right >= 0 && right < this.pages.length)  chunkParts.push(this.pages[right]);
    const chunk = chunkParts.join(' ').slice(0, 480);

    // AI narrator commentary (every N turns, not at very end)
    this.turnsSinceCommentary++;
    const atEnd = (this.currentSpread + 1) >= this.totalSpreads;
    if (this.turnsSinceCommentary >= this.commentaryEvery && !atEnd) {
      this.turnsSinceCommentary = 0;
      const commentary = await this.fetchCommentary(chunk);
      if (commentary && !this.isPaused) {
        await this.showBubble(commentary);
        await this.speak(commentary);
        await this.pauseAware(400);
        await this.hideBubble();
      }
    }

    if (this.isPaused) { this._pendingResume = true; return; }

    // Check if we've reached the end
    const nextRight = (this.currentSpread + 1) * 2;
    const nextLeft  = (this.currentSpread + 1) * 2 - 1;
    const noMoreContent = nextRight >= this.pages.length && nextLeft >= this.pages.length;

    if (noMoreContent || (right >= this.pages.length - 1 && this.currentSpread >= this.totalSpreads - 1)) {
      this.isFinished = true;
      await this.pauseAware(1200);
      await this.speak(
        'And so our story draws to its close. ' +
        'What a wonderful journey we have shared together. ' +
        'I do hope it brought you joy.'
      );
      this.dom.pauseIcon.textContent  = '✓';
      this.dom.pauseLabel.textContent = 'Finished';
      this.dom.pauseBtn.disabled = true;
      return;
    }

    // Turn the page
    await this.turnPage();

    this.currentSpread++;
    this.loadSpread(this.currentSpread);

    await this.pauseAware(600);
    this.narrateCurrentSpread();
  }

  // ── Pause-aware delay ───────────────────────────────────────────────────────

  pauseAware(ms) {
    return new Promise(resolve => {
      const end = Date.now() + ms;
      const tick = () => {
        if (this.isPaused) {
          setTimeout(tick, 80);
        } else if (Date.now() >= end) {
          resolve();
        } else {
          setTimeout(tick, Math.min(80, end - Date.now()));
        }
      };
      tick();
    });
  }

  // ── Speech Synthesis ────────────────────────────────────────────────────────

  speak(text) {
    if (!text || !text.trim()) return Promise.resolve();

    return new Promise(resolve => {
      speechSynthesis.cancel();

      const utt = new SpeechSynthesisUtterance(text);
      if (this.narratorVoice) utt.voice = this.narratorVoice;
      utt.rate   = this.speechRate;
      utt.pitch  = 1.08;
      utt.volume = this.speechVolume;

      utt.onstart = () => {
        this.isSpeaking = true;
        this.dom.narratorIndicator.classList.add('speaking');
      };

      utt.onend = () => {
        this.isSpeaking = false;
        this.dom.narratorIndicator.classList.remove('speaking');
        resolve();
      };

      utt.onerror = e => {
        if (e.error === 'interrupted') { resolve(); return; }
        console.warn('[TTS error]', e.error);
        this.isSpeaking = false;
        this.dom.narratorIndicator.classList.remove('speaking');
        resolve();
      };

      speechSynthesis.speak(utt);
    });
  }

  // ── Pause / Resume ──────────────────────────────────────────────────────────

  togglePause() {
    this.isPaused = !this.isPaused;
    const { pauseIcon, pauseLabel } = this.dom;

    if (this.isPaused) {
      speechSynthesis.pause();
      pauseIcon.textContent  = '▶';
      pauseLabel.textContent = 'Resume';
    } else {
      pauseIcon.textContent  = '⏸';
      pauseLabel.textContent = 'Pause';

      // If we were mid-speech, resume; otherwise restart narration
      if (speechSynthesis.paused) {
        speechSynthesis.resume();
      }

      // If narration was waiting on pause, continue it
      if (this._pendingResume) {
        this._pendingResume = false;
        setTimeout(() => this.narrateCurrentSpread(), 300);
      }
    }
  }

  // ── AI Commentary ───────────────────────────────────────────────────────────

  async fetchCommentary(text) {
    try {
      const resp = await fetch('/api/narrator', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text,
          pageNumber:   this.currentSpread + 1,
          totalSpreads: this.totalSpreads,
          bookTitle:    this.bookTitle,
        }),
        signal: AbortSignal.timeout(9000),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      return data.commentary || null;
    } catch (err) {
      console.warn('[Commentary fetch]', err.message);
      return this.fallbackLine();
    }
  }

  fallbackLine() {
    const lines = [
      "Oh, what a passage! I wonder what's in store for us next... shall we turn the page and find out?",
      "Isn't that remarkable! Let's keep reading — I have a feeling things are about to get very interesting.",
      "Well now, I didn't quite expect that! Let's see where the story takes us next.",
      "What do you think about all of that? Remarkable! Come along now — let's read on.",
      "Oh my, things are certainly developing! Onward we go — I can hardly wait to see what happens!",
    ];
    return lines[Math.floor(Math.random() * lines.length)];
  }

  // ── Narrator Bubble ─────────────────────────────────────────────────────────

  async showBubble(text) {
    this.dom.bubbleText.textContent = text;
    this.dom.narratorBubble.classList.add('visible');
    await delay(250);
  }

  async hideBubble() {
    this.dom.narratorBubble.classList.remove('visible');
    await delay(500);
  }

  // ── Progress ─────────────────────────────────────────────────────────────────

  updateProgress(spreadIndex) {
    const pct = this.totalSpreads > 1
      ? (spreadIndex / (this.totalSpreads - 1)) * 100
      : 100;
    this.dom.progressFill.style.width = pct.toFixed(1) + '%';

    const { left, right } = this.getSpreadIndices(spreadIndex);
    const lo = Math.max(1, left + 1);
    const hi = Math.min(right + 1, this.pages.length);
    if (left < 0) {
      this.dom.pageIndicator.textContent = `Page 1 of ${this.pages.length}`;
    } else {
      this.dom.pageIndicator.textContent = `Pages ${lo}–${hi} of ${this.pages.length}`;
    }
  }
}

// ── Bootstrap ─────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  new ParticleSystem();
  new StoryBook();
});
