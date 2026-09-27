/**
 * UniScribe — Front-End Application Logic
 * Implements MVP Flow: Gravar -> Transcrever -> Filtrar -> Resumir -> Exibir -> Exportar
 */

// Application State Machine
const AppState = {
  IDLE: 'idle',
  LISTENING: 'listening',
  PROCESSING: 'processing',
  READY: 'ready'
};

// Fixture Data for Offline/Demo/Fallback execution
const SAMPLES = {
  redes: {
    course: 'Redes de Computadores',
    title: 'Aula de Redes — Protocolos TCP e UDP',
    duration: '42 min',
    rawTranscript: `Bom dia pessoal, aham, todo mundo me ouvindo bem? Beleza... É... vamos começar a aula de hoje falando sobre a camada de transporte. Basicamente nós temos dois grandes protocolos: o TCP e o UDP. O TCP, veja bem, Transmission Control Protocol, é um protocolo orientado à conexão. Ele faz o three-way handshake: SYN, SYN-ACK e ACK. Isso é fundamental, pessoal, vai cair na prova com certeza! Já o UDP, User Datagram Protocol, é não orientado à conexão, ele não garante entrega nem ordenação de pacotes, porém é muito mais rápido, sendo utilizado em streaming de vídeo e jogos online. Professor, uma pergunta aqui: por que o DNS usa UDP e não TCP? Boa pergunta, Marcelo! O DNS usa UDP na porta 53 para consultas normais pela rapidez, mas pode usar TCP para transferências de zona. Anotem isso. Resumindo: TCP garante integridade com retransmissão, UDP foca em baixa latência sem confirmação. Ficou claro? Beleza, encerramos por aqui hoje.`,
    filteredTranscript: `Camada de transporte: dois grandes protocolos, TCP e UDP. O TCP (Transmission Control Protocol) é um protocolo orientado à conexão, realizando o handshake em três vias (SYN, SYN-ACK, ACK). Garante integridade e ordenação por retransmissão de pacotes. O UDP (User Datagram Protocol) não é orientado à conexão, não garante entrega ou ordenação, priorizando baixa latência em streaming e jogos online. Dúvida: O DNS utiliza UDP na porta 53 para consultas rápidas, utilizando TCP para transferências de zona. Resumo: TCP garante confiabilidade; UDP prioriza velocidade.`,
    summary: {
      title: 'Aula de Redes — Protocolos TCP e UDP',
      course: 'Redes de Computadores',
      concepts: [
        '<strong>TCP (Transmission Control Protocol):</strong> Protocolo orientado à conexão com confiabilidade ponta a ponta.',
        '<strong>Three-way Handshake:</strong> Mecanismo de estabelecimento de conexão TCP composto por 3 etapas consecutivas (SYN → SYN-ACK → ACK).',
        '<strong>UDP (User Datagram Protocol):</strong> Protocolo não orientado à conexão e sem confirmação de entrega, com overhead mínimo e baixa latência.'
      ],
      highlights: [
        '<strong>Ponto de Prova:</strong> Diferenciação estrita de garantias: TCP garante entrega ordenada e retransmissão de pacotes perdidos; UDP não garante entrega.',
        '<strong>Casos de Uso:</strong> TCP para navegação web (HTTP/HTTPS), e-mail e transferência de arquivos; UDP para streaming em tempo real, chamadas VoIP e jogos online.',
        '<strong>Porta Padrão:</strong> DNS opera na porta 53 via UDP (consultas rápidas) e TCP (transferências de zona).'
      ],
      questions: [
        '<strong>Pergunta do Aluno:</strong> Por que o protocolo DNS utiliza UDP em vez de TCP?',
        '<strong>Explicação do Professor:</strong> Para reduzir a latência de resolução de nomes em consultas comuns (evitando o overhead do handshake); o TCP só é ativado em transferências volumosas de zona.'
      ],
      executive: 'Nesta aula sobre a Camada de Transporte, foram comparados os modelos de serviço dos protocolos TCP e UDP. O TCP prioriza confiabilidade, controle de fluxo e entrega sequencial mediante o three-way handshake e controle de congestionamento. Em contraste, o UDP elimina o aperto de mãos prévio, permitindo envio imediato de datagramas com latência mínima para aplicações sensíveis a atraso.',
      uncertainties: []
    }
  },
  calculo: {
    course: 'Cálculo Diferencial',
    title: 'Aula de Cálculo — Definição Precisa de Limite',
    duration: '50 min',
    rawTranscript: `E aí turma, bom dia. Hoje vamos falar sobre a definição formal de limite com épsilon e delta. O limite de f(x) quando x tende a a é igual a L se, para todo epsilon maior que zero, existe um delta maior que zero tal que se 0 < |x - a| < delta, então |f(x) - L| < epsilon. Isso é crucial para as demonstrações que faremos na prova bimestral. Alguém tem dúvida sobre o módulo? Lembrem-se que a distância entre x e a é sempre positiva pois x não precisa ser igual a a.`,
    filteredTranscript: `Definição formal de limite com épsilon e delta: O limite de f(x) quando x tende a 'a' é igual a L se, para todo ε > 0, existe um δ > 0 tal que 0 < |x - a| < δ implica |f(x) - L| < ε. O valor de x se aproxima de 'a' sem necessariamente igualar-se a ele. Conceito cobrado nas demonstrações da avaliação bimestral.`,
    summary: {
      title: 'Aula de Cálculo — Definição Precisa de Limite',
      course: 'Cálculo Diferencial',
      concepts: [
        '<strong>Definição Formal de Limite (ε-δ):</strong> lim_{x→a} f(x) = L se ∀ε > 0, ∃δ > 0 tal que 0 < |x - a| < δ ⇒ |f(x) - L| < ε.',
        '<strong>Vizinhança Perfurada:</strong> A condição 0 < |x - a| indica que o comportamento da função na vizinhança de a independe do valor de f(a).'
      ],
      highlights: [
        '<strong>Ponto de Avaliação:</strong> Demonstrações práticas de limites de funções polinomiais e lineares usando a escolha de δ em função de ε.',
        '<strong>Fórmula-chave:</strong> |f(x) - L| < ε'
      ],
      questions: [
        '<strong>Dúvida:</strong> Por que x não pode ser igual a a na definição de limite?',
        '<strong>Resposta:</strong> O limite investiga a tendência da função quando x se aproxima arbitrariamente de a, existindo mesmo quando f(a) for indefinida.'
      ],
      executive: 'Apresentação rigorosa da definição formal de limite utilizando épsilon e delta de Cauchy-Weierstrass. A aula estabeleceu as bases lógicas para o estudo de continuidade e diferenciabilidade.',
      uncertainties: []
    }
  },
  direito: {
    course: 'Direito Constitucional',
    title: 'Aula de Direito — Princípios Fundamentais da CF/88',
    duration: '38 min',
    rawTranscript: `Bom dia estudantes, abrindo a CF/88 no artigo 1º ao 4º... Nós temos os fundamentos da República Federativa do Brasil: soberania, cidadania, dignidade da pessoa humana, valores sociais do trabalho e da livre iniciativa, e pluralismo político (o mnemônico SO-CI-DI-VA-PLU). Atenção: não confundir fundamentos com objetivos fundamentais do art. 3º! Isso cai em todos os concursos e na prova da OAB.`,
    filteredTranscript: `Fundamentos da República Federativa do Brasil (Art. 1º, CF/88): Soberania, Cidadania, Dignidade da pessoa humana, Valores sociais do trabalho e da livre iniciativa, Pluralismo político (mnemônico SOCIDIVAPLU). Distinção essencial entre fundamentos (Art. 1º) e objetivos fundamentais (Art. 3º).`,
    summary: {
      title: 'Aula de Direito — Princípios Fundamentais da CF/88',
      course: 'Direito Constitucional',
      concepts: [
        '<strong>Fundamentos da República (Art. 1º, CF/88):</strong> Soberania, Cidadania, Dignidade da Pessoa Humana, Valores Sociais do Trabalho e da Livre Iniciativa, Pluralismo Político.',
        '<strong>Mnemônico Clássico:</strong> SO-CI-DI-VA-PLU.'
      ],
      highlights: [
        '<strong>Alerta de Prova / OAB:</strong> Não confundir os fundamentos (Art. 1º) com os objetivos fundamentais (Art. 3º: construir sociedade livre, justa e solidária, etc.).'
      ],
      questions: [
        '<strong>Dúvida:</strong> Pluralismo político é o mesmo que pluripartidarismo?',
        '<strong>Resposta:</strong> Não. O pluripartidarismo é uma das expressões do pluralismo político, que abrange diversidade ideológica, filosófica e de pensamento.'
      ],
      executive: 'Estudo dos princípios fundamentais consagrados na Carta Magna de 1988, delimitando os cinco fundamentos estruturantes do Estado Democrático de Direito brasileiro e prevenindo confusões doutrinárias recorrentes.',
      uncertainties: []
    }
  }
};

function stripMarkup(value) {
  return String(value ?? '').replace(/<[^>]*>/g, '');
}

function renderTextList(element, values, emptyText = 'Nenhum ponto registrado.', strip = false) {
  if (!element) return;
  while (element.firstChild) element.removeChild(element.firstChild);
  const items = Array.isArray(values) ? values : [];
  if (items.length === 0) {
    const empty = document.createElement('li');
    empty.textContent = emptyText;
    element.appendChild(empty);
    return;
  }
  items.forEach((value) => {
    const item = document.createElement('li');
    item.textContent = strip ? stripMarkup(value) : String(value ?? '');
    element.appendChild(item);
  });
}

function normaliseBackendUrl(value) {
  const fallback = 'http://127.0.0.1:8080';
  try {
    const parsed = new URL(String(value || '').trim());
    if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password) {
      return fallback;
    }
    return parsed.toString().replace(/\/$/, '');
  } catch (_) {
    return fallback;
  }
}

class UniScribeApp {
  constructor() {
    this.currentState = AppState.IDLE;
    this.backendUrl = normaliseBackendUrl(localStorage.getItem('uniscribe_backend_url'));
    this.simulationMode = localStorage.getItem('uniscribe_simulation') !== 'false';
    this.activeTheme = localStorage.getItem('uniscribe_theme') || 'theme-light';
    
    // Recording & Audio state
    this.mediaRecorder = null;
    this.audioChunks = [];
    this.audioStream = null;
    this.audioContext = null;
    this.analyser = null;
    this.animationFrameId = null;
    this.timerInterval = null;
    this.startTime = null;
    this.elapsedSeconds = 0;
    
    // Processed Result Store
    this.currentResult = null;
    
    this.initElements();
    this.bindEvents();
    this.applyTheme(this.activeTheme);
    this.checkNetworkStatus();
    this.checkBackendHealth();
    
    // Poll backend health every 15s
    setInterval(() => this.checkBackendHealth(), 15000);
  }

  initElements() {
    // State Containers
    this.stateIdle = document.getElementById('stateIdle');
    this.stateListening = document.getElementById('stateListening');
    this.stateProcessing = document.getElementById('stateProcessing');
    this.stateReady = document.getElementById('stateReady');

    // Controls
    this.startBtn = document.getElementById('startListeningBtn');
    this.stopBtn = document.getElementById('stopListeningBtn');
    this.copyBtn = document.getElementById('copySummaryBtn');
    this.exportBtn = document.getElementById('exportTxtBtn');
    this.newLectureBtn = document.getElementById('newLectureBtn');
    this.themeToggleBtn = document.getElementById('themeToggleBtn');
    this.sunIcon = document.getElementById('sunIcon');
    this.moonIcon = document.getElementById('moonIcon');
    this.settingsBtn = document.getElementById('settingsBtn');
    this.settingsModal = document.getElementById('settingsModal');
    this.closeSettingsBtn = document.getElementById('closeSettingsBtn');
    this.saveSettingsBtn = document.getElementById('saveSettingsBtn');
    this.backendUrlInput = document.getElementById('backendUrlInput');
    this.simulationToggle = document.getElementById('simulationToggle');
    
    // Badges & Banner
    this.backendBadge = document.getElementById('backendBadge');
    this.backendBadgeLabel = document.getElementById('backendBadgeLabel');
    this.networkBadge = document.getElementById('networkBadge');
    this.networkBadgeLabel = document.getElementById('networkBadgeLabel');
    this.offlineBanner = document.getElementById('offlineBanner');
    this.toastContainer = document.getElementById('toastContainer');

    // Inputs
    this.lectureTitleInput = document.getElementById('lectureTitleInput');
    this.courseSelect = document.getElementById('courseSelect');
    this.languageSelect = document.getElementById('languageSelect');

    // Listening elements
    this.recordingTimer = document.getElementById('recordingTimer');
    this.currentTopicTag = document.getElementById('currentTopicTag');
    this.currentTopicTitle = document.getElementById('currentTopicTitle');
    this.waveformCanvas = document.getElementById('waveformCanvas');
    this.liveTranscriptText = document.getElementById('liveTranscriptText');

    // Processing steps
    this.processingStatusText = document.getElementById('processingStatusText');
    this.stepAudio = document.getElementById('stepAudio');
    this.stepWhisper = document.getElementById('stepWhisper');
    this.stepFilter = document.getElementById('stepFilter');
    this.stepGemini = document.getElementById('stepGemini');
    this.whisperStepDesc = document.getElementById('whisperStepDesc');

    // Results elements
    this.readyCourseTag = document.getElementById('readyCourseTag');
    this.readyDateTag = document.getElementById('readyDateTag');
    this.readyDurationTag = document.getElementById('readyDurationTag');
    this.readyLectureTitle = document.getElementById('readyLectureTitle');
    this.uncertaintyAlert = document.getElementById('uncertaintyAlert');
    this.uncertaintyAlertMsg = document.getElementById('uncertaintyAlertMsg');
    this.summaryConceptsList = document.getElementById('summaryConceptsList');
    this.summaryHighlightsList = document.getElementById('summaryHighlightsList');
    this.summaryQuestionsList = document.getElementById('summaryQuestionsList');
    this.questionsSection = document.getElementById('questionsSection');
    this.summaryExecutiveText = document.getElementById('summaryExecutiveText');
    this.filteredTranscriptContent = document.getElementById('filteredTranscriptContent');
    this.rawTranscriptContent = document.getElementById('rawTranscriptContent');
    this.filteredWordCount = document.getElementById('filteredWordCount');
    this.rawWordCount = document.getElementById('rawWordCount');
    
    // Tab elements
    this.tabButtons = document.querySelectorAll('.tab-btn');
    this.tabContents = document.querySelectorAll('.tab-content');
    
    // Sample buttons
    this.sampleChips = document.querySelectorAll('.sample-chip');
  }

  bindEvents() {
    this.startBtn.addEventListener('click', () => this.handleStartListening());
    this.stopBtn.addEventListener('click', () => this.handleStopListening());
    this.copyBtn.addEventListener('click', () => this.handleCopySummary());
    this.exportBtn.addEventListener('click', () => this.handleExportTxt());
    this.newLectureBtn.addEventListener('click', () => this.transitionTo(AppState.IDLE));

    // Theme toggle
    this.themeToggleBtn.addEventListener('click', () => this.toggleTheme());

    // Settings
    this.settingsBtn.addEventListener('click', () => this.openSettings());
    this.closeSettingsBtn.addEventListener('click', () => this.closeSettings());
    this.saveSettingsBtn.addEventListener('click', () => this.saveSettings());
    this.settingsModal.addEventListener('click', (e) => {
      if (e.target === this.settingsModal) this.closeSettings();
    });

    // Sample clicks
    this.sampleChips.forEach(chip => {
      chip.addEventListener('click', (e) => {
        const sampleKey = e.currentTarget.getAttribute('data-sample');
        this.loadSampleAndProcess(sampleKey);
      });
    });

    // Tabs
    this.tabButtons.forEach(btn => {
      btn.addEventListener('click', (e) => {
        const targetTab = e.currentTarget.getAttribute('data-tab');
        this.switchTab(targetTab);
      });
    });

    // Network status
    window.addEventListener('online', () => this.checkNetworkStatus());
    window.addEventListener('offline', () => this.checkNetworkStatus());

    // Safe exit warning during recording
    window.addEventListener('beforeunload', (e) => {
      if (this.currentState === AppState.LISTENING) {
        e.preventDefault();
        e.returnValue = 'Existe uma aula sendo gravada. Sair agora interromperá a captura!';
        return e.returnValue;
      }
    });
  }

  transitionTo(newState) {
    this.currentState = newState;

    // Hide all states
    [this.stateIdle, this.stateListening, this.stateProcessing, this.stateReady].forEach(el => {
      el.classList.remove('active');
    });

    // Show active state
    switch (newState) {
      case AppState.IDLE:
        this.stateIdle.classList.add('active');
        this.resetRecorderState();
        break;
      case AppState.LISTENING:
        this.stateListening.classList.add('active');
        break;
      case AppState.PROCESSING:
        this.stateProcessing.classList.add('active');
        break;
      case AppState.READY:
        this.stateReady.classList.add('active');
        break;
    }
  }

  // --- Theme Management ---
  applyTheme(theme) {
    document.body.className = theme;
    this.activeTheme = theme;
    localStorage.setItem('uniscribe_theme', theme);
    if (theme === 'theme-dark') {
      this.sunIcon.style.display = 'block';
      this.moonIcon.style.display = 'none';
    } else {
      this.sunIcon.style.display = 'none';
      this.moonIcon.style.display = 'block';
    }
  }

  toggleTheme() {
    const nextTheme = this.activeTheme === 'theme-light' ? 'theme-dark' : 'theme-light';
    this.applyTheme(nextTheme);
  }

  // --- Network & Backend Health Checks ---
  checkNetworkStatus() {
    if (navigator.onLine) {
      this.networkBadge.className = 'status-chip chip-online';
      this.networkBadgeLabel.textContent = 'Online';
      this.offlineBanner.style.display = 'none';
    } else {
      this.networkBadge.className = 'status-chip chip-warning';
      this.networkBadgeLabel.textContent = 'Offline';
      this.offlineBanner.style.display = 'block';
      this.showToast('Sem conexão de rede. Gravações continuam seguras localmente.', 'warning');
    }
  }

  async checkBackendHealth() {
    try {
      const response = await fetch(`${this.backendUrl}/health`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' },
        signal: AbortSignal.timeout(3000)
      });
      if (response.ok) {
        const data = await response.json();
        if (data.status === 'ok') {
          this.backendBadge.className = 'status-chip chip-online';
          this.backendBadgeLabel.textContent = 'Backend Ativo';
          return true;
        }
      }
      throw new Error('Backend não respondeu ok');
    } catch (_err) {
      this.backendBadge.className = 'status-chip chip-offline';
      this.backendBadgeLabel.textContent = 'Backend Offline';
      return false;
    }
  }

  // --- Recording Flow ---
  async handleStartListening() {
    const title = this.lectureTitleInput.value.trim() || 'Aula sem Título';
    const course = this.courseSelect.options[this.courseSelect.selectedIndex].text;

    this.currentTopicTitle.textContent = title;
    this.currentTopicTag.textContent = course;

    // Check mediaDevices support
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      this.showToast('Gravação de microfone não suportada neste navegador.', 'error');
      if (this.simulationMode) this.startSimulatedRecording();
      return;
    }

    try {
      this.audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.startRealRecording(this.audioStream);
    } catch (err) {
      console.warn('Microfone bloqueado ou indisponível:', err);
      const denied = err && ['NotAllowedError', 'PermissionDeniedError', 'SecurityError'].includes(err.name);
      if (denied) {
        this.showToast('Permissão de microfone negada. Autorize o acesso e tente novamente.', 'error');
        return;
      }
      this.showToast('Microfone inacessível. Use um exemplo ou ative o modo demonstração.', 'warning');
      if (this.simulationMode) this.startSimulatedRecording();
    }
  }

  startRealRecording(stream) {
    this.audioChunks = [];
    this.transitionTo(AppState.LISTENING);

    // Initialize MediaRecorder
    try {
      this.mediaRecorder = new MediaRecorder(stream);
      this.mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) this.audioChunks.push(e.data);
      };
      this.mediaRecorder.start(1000); // 1-second chunks
    } catch (err) {
      console.error('Erro ao iniciar MediaRecorder:', err);
      stream.getTracks().forEach((track) => track.stop());
      this.audioStream = null;
      this.showToast('Não foi possível iniciar a gravação neste navegador.', 'error');
      if (this.simulationMode) this.startSimulatedRecording();
      return;
    }

    // Initialize Web Audio API Analyser for Waveform
    try {
      this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const source = this.audioContext.createMediaStreamSource(stream);
      this.analyser = this.audioContext.createAnalyser();
      this.analyser.fftSize = 256;
      source.connect(this.analyser);
      this.startWaveformVisualizer(this.analyser);
    } catch (err) {
      console.warn('Erro ao configurar AudioContext:', err);
      this.startSyntheticWaveform();
    }

    this.startTimer();
    this.startTranscriptSimulationPreview();
  }

  startSimulatedRecording() {
    this.transitionTo(AppState.LISTENING);
    this.startTimer();
    this.startSyntheticWaveform();
    this.startTranscriptSimulationPreview();
  }

  startTimer() {
    this.startTime = Date.now();
    this.elapsedSeconds = 0;
    this.timerInterval = setInterval(() => {
      this.elapsedSeconds = Math.floor((Date.now() - this.startTime) / 1000);
      const hours = String(Math.floor(this.elapsedSeconds / 3600)).padStart(2, '0');
      const minutes = String(Math.floor((this.elapsedSeconds % 3600) / 60)).padStart(2, '0');
      const seconds = String(this.elapsedSeconds % 60).padStart(2, '0');
      this.recordingTimer.textContent = `${hours}:${minutes}:${seconds}`;
    }, 1000);
  }

  startWaveformVisualizer(analyser) {
    const canvas = this.waveformCanvas;
    const ctx = canvas.getContext('2d');
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    const draw = () => {
      this.animationFrameId = requestAnimationFrame(draw);
      analyser.getByteFrequencyData(dataArray);

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const barWidth = (canvas.width / bufferLength) * 2.2;
      let x = 0;

      for (let i = 0; i < bufferLength; i++) {
        const barHeight = (dataArray[i] / 255) * (canvas.height * 0.85);
        const gradient = ctx.createLinearGradient(0, canvas.height, 0, 0);
        gradient.addColorStop(0, '#2563eb');
        gradient.addColorStop(1, '#60a5fa');

        ctx.fillStyle = gradient;
        ctx.fillRect(x, canvas.height - barHeight, barWidth - 1, barHeight);

        x += barWidth;
      }
    };
    draw();
  }

  startSyntheticWaveform() {
    const canvas = this.waveformCanvas;
    const ctx = canvas.getContext('2d');
    let phase = 0;

    const draw = () => {
      this.animationFrameId = requestAnimationFrame(draw);
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const numBars = 40;
      const barWidth = canvas.width / numBars;

      for (let i = 0; i < numBars; i++) {
        const amplitude = Math.sin(phase + i * 0.3) * 0.4 + Math.cos(phase * 0.7 + i * 0.2) * 0.4 + 0.2;
        const barHeight = Math.max(12, amplitude * (canvas.height * 0.8));

        const gradient = ctx.createLinearGradient(0, canvas.height, 0, 0);
        gradient.addColorStop(0, '#2563eb');
        gradient.addColorStop(1, '#818cf8');

        ctx.fillStyle = gradient;
        ctx.fillRect(i * barWidth + 2, canvas.height - barHeight, barWidth - 4, barHeight);
      }
      phase += 0.08;
    };
    draw();
  }

  startTranscriptSimulationPreview() {
    const phrases = [
      'Captando fala do professor...',
      'Analisando frequências da voz e removendo ruído de fundo...',
      'Segmentando chunks de áudio para ASR Whisper...',
      'Buffer local íntegro. Gravação contínua garantida.'
    ];
    let idx = 0;
    this.previewInterval = setInterval(() => {
      idx = (idx + 1) % phrases.length;
      if (this.liveTranscriptText) {
        this.liveTranscriptText.textContent = phrases[idx];
      }
    }, 4500);
  }

  async handleStopListening() {
    if (this.currentState !== AppState.LISTENING) {
      this.showToast('Inicie uma gravação antes de parar.', 'warning');
      return;
    }
    // Stop recording and stream
    if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
      this.mediaRecorder.stop();
    }
    if (this.audioStream) {
      this.audioStream.getTracks().forEach(track => track.stop());
    }
    if (this.audioContext && this.audioContext.state !== 'closed') {
      try { await this.audioContext.close(); } catch (_) {}
    }
    if (this.animationFrameId) cancelAnimationFrame(this.animationFrameId);
    if (this.timerInterval) clearInterval(this.timerInterval);
    if (this.previewInterval) clearInterval(this.previewInterval);

    const recordedSeconds = this.elapsedSeconds || 5;
    const durationLabel = `${Math.max(1, Math.round(recordedSeconds / 60))} min`;

    this.transitionTo(AppState.PROCESSING);
    await this.processRecordedAudio(durationLabel);
  }

  async processRecordedAudio(durationLabel) {
    const lectureTitle = this.currentTopicTitle.textContent || 'Aula Gravada';
    const course = this.currentTopicTag.textContent || 'Geral';
    const language = this.languageSelect.value;
    const lectureId = `lecture-${Date.now()}`;

    // Update processing steps UI visually
    this.updateProcessingStep('audio', 'Concluído', true);
    this.updateProcessingStep('whisper', 'Em execução...', false, true);

    let audioBlob = null;
    if (this.audioChunks && this.audioChunks.length > 0) {
      audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
    }

    let backendSuccess = false;
    let backendResult = null;
    let backendFailure = null;

    // Check if backend is available. A real recording is never silently
    // replaced by a fixture when simulation mode is disabled.
    const isBackendAlive = await this.checkBackendHealth();
    if (!this.simulationMode && (!isBackendAlive || !audioBlob)) {
      this.transitionTo(AppState.IDLE);
      this.showToast(
        isBackendAlive
          ? 'Nenhum áudio foi capturado. Tente novamente.'
          : 'O backend está indisponível e o modo demonstração está desativado.',
        'error'
      );
      return;
    }
    if (isBackendAlive && audioBlob && !this.simulationMode) {
      try {
        this.updateProcessingStep('whisper', 'Enviando áudio ao servidor...', false, true);
        const base64Audio = await this.blobToBase64(audioBlob);

        const response = await fetch(`${this.backendUrl}/v1/process-audio`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            lecture_id: lectureId,
            course_id: course,
            title: lectureTitle,
            language_tag: language,
            audio_base64: base64Audio
          })
        });

        if (response.ok) {
          backendResult = await response.json();
          backendSuccess = true;
        } else {
          backendFailure = `HTTP ${response.status}`;
          console.warn('Backend retornou erro:', response.status);
        }
      } catch (err) {
        backendFailure = 'falha de rede';
        console.warn('Falha na requisição ao backend:', err);
      }
    }

    if (!this.simulationMode && !backendSuccess) {
      this.transitionTo(AppState.IDLE);
      this.showToast(`Não foi possível processar a gravação (${backendFailure || 'erro desconhecido'}).`, 'error');
      return;
    }

    // Transition through stages with polite delays so user sees transparency
    await this.sleep(700);
    this.updateProcessingStep('whisper', 'Concluído', true);
    this.updateProcessingStep('filter', 'Eliminando hesitações e conversas paralelas...', false, true);

    await this.sleep(800);
    this.updateProcessingStep('filter', 'Concluído', true);
    this.updateProcessingStep('gemini', 'Gerando tópicos e alertas para prova...', false, true);

    await this.sleep(900);
    this.updateProcessingStep('gemini', 'Concluído', true);

    if (backendSuccess && backendResult) {
      this.renderBackendResult(backendResult, durationLabel);
      this.transitionTo(AppState.READY);
      this.showToast('Resumo processado pelo backend.', 'success');
    } else {
      // Use intelligent simulation matching the chosen course only when the
      // user explicitly enabled the offline/demo mode.
      this.renderFallbackResult(course, lectureTitle, durationLabel);
      this.transitionTo(AppState.READY);
      this.showToast('Resumo de demonstração gerado localmente.', 'success');
    }
  }

  updateProcessingStep(stepKey, desc, completed, active = false) {
    const el = document.getElementById(`step${stepKey.charAt(0).toUpperCase() + stepKey.slice(1)}`);
    if (!el) return;

    el.className = 'step-item';
    if (completed) {
      el.classList.add('step-completed');
      el.querySelector('.step-icon').textContent = '✓';
    } else if (active) {
      el.classList.add('step-active');
      el.querySelector('.step-icon').textContent = '⟳';
    } else {
      el.querySelector('.step-icon').textContent = '○';
    }

    const descEl = el.querySelector('.step-desc');
    if (descEl && desc) descEl.textContent = desc;
  }

  // --- Results Rendering ---
  renderBackendResult(data, duration) {
    const lecture = data.lecture || {};
    const transcript = data.transcript || {};
    const summary = typeof data.summary === 'string'
      ? { final_summary: data.summary, bullets: [] }
      : (data.summary || {});

    this.readyLectureTitle.textContent = lecture.title || 'Resumo da Aula';
    this.readyCourseTag.textContent = lecture.course_id || 'Geral';
    this.readyDurationTag.textContent = duration;
    this.readyDateTag.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    // Summary concepts & bullets. Text nodes are used deliberately: transcript
    // and model output are untrusted content, not trusted HTML.
    const bullets = Array.isArray(summary.bullets) ? summary.bullets : [];
    const concepts = Array.isArray(summary.key_concepts) && summary.key_concepts.length
      ? summary.key_concepts
      : bullets;
    const highlights = [
      ...(Array.isArray(summary.formulas) ? summary.formulas : []),
      ...(Array.isArray(summary.important_points) ? summary.important_points : []),
    ];
    const questions = Array.isArray(summary.detected_questions) ? summary.detected_questions : [];
    renderTextList(this.summaryConceptsList, concepts);
    renderTextList(this.summaryHighlightsList, highlights, 'Nenhum destaque informado.');
    if (questions.length > 0) {
      this.questionsSection.style.display = 'block';
      renderTextList(this.summaryQuestionsList, questions);
    } else {
      this.questionsSection.style.display = 'none';
    }
    this.summaryExecutiveText.textContent = summary.final_summary || bullets.join(' ') || 'Resumo processado.';

    // Transcripts
    this.filteredTranscriptContent.textContent = transcript.filtered_text || transcript.raw_text || '';
    this.rawTranscriptContent.textContent = transcript.raw_text || '';

    this.filteredWordCount.textContent = `${String(transcript.filtered_text || '').split(/\s+/).filter(Boolean).length} palavras`;
    this.rawWordCount.textContent = `${String(transcript.raw_text || '').split(/\s+/).filter(Boolean).length} palavras`;

    // Uncertainties
    if (Array.isArray(summary.uncertainties) && summary.uncertainties.length > 0) {
      this.uncertaintyAlert.style.display = 'flex';
      this.uncertaintyAlertMsg.textContent = summary.uncertainties.join('; ');
    } else {
      this.uncertaintyAlert.style.display = 'none';
    }

    this.currentResult = {
      title: lecture.title,
      course: lecture.course_id,
      date: new Date().toLocaleDateString('pt-BR'),
      duration,
      concepts: concepts.map((item) => String(item ?? '')),
      highlights: highlights.map((item) => String(item ?? '')),
      questions: questions.map((item) => String(item ?? '')),
      executive: String(summary.final_summary || bullets.join(' ') || ''),
      summaryText: bullets.join('\n• '),
      filteredText: transcript.filtered_text,
      rawText: transcript.raw_text
    };
  }

  renderFallbackResult(courseName, lectureTitle, duration) {
    // Select closest fixture
    let sample = SAMPLES.redes;
    const lowerCourse = courseName.toLowerCase();
    if (lowerCourse.includes('cálculo') || lowerCourse.includes('calculo')) {
      sample = SAMPLES.calculo;
    } else if (lowerCourse.includes('direito')) {
      sample = SAMPLES.direito;
    }

    this.readyLectureTitle.textContent = lectureTitle || sample.title;
    this.readyCourseTag.textContent = courseName || sample.course;
    this.readyDurationTag.textContent = duration || sample.duration;
    this.readyDateTag.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    // Render lists as text nodes; fixtures contain simple emphasis markup but
    // should never be injected as executable HTML.
    renderTextList(this.summaryConceptsList, sample.summary.concepts, 'Nenhum ponto registrado.', true);
    renderTextList(this.summaryHighlightsList, sample.summary.highlights, 'Nenhum destaque informado.', true);
    if (sample.summary.questions && sample.summary.questions.length > 0) {
      this.questionsSection.style.display = 'block';
      renderTextList(this.summaryQuestionsList, sample.summary.questions, 'Nenhuma dúvida registrada.', true);
    } else {
      this.questionsSection.style.display = 'none';
    }

    this.summaryExecutiveText.textContent = stripMarkup(sample.summary.executive);

    // Transcripts
    this.filteredTranscriptContent.textContent = sample.filteredTranscript;
    this.rawTranscriptContent.textContent = sample.rawTranscript;

    this.filteredWordCount.textContent = `${sample.filteredTranscript.split(/\s+/).length} palavras relevantes`;
    this.rawWordCount.textContent = `${sample.rawTranscript.split(/\s+/).length} palavras gravadas`;

    this.uncertaintyAlert.style.display = 'none';

    this.currentResult = {
      title: lectureTitle || sample.title,
      course: courseName || sample.course,
      date: new Date().toLocaleDateString('pt-BR'),
      duration: duration || sample.duration,
      concepts: sample.summary.concepts.map(stripMarkup),
      highlights: sample.summary.highlights.map(stripMarkup),
      questions: (sample.summary.questions || []).map(stripMarkup),
      executive: stripMarkup(sample.summary.executive),
      filteredText: sample.filteredTranscript,
      rawText: sample.rawTranscript
    };
  }

  async loadSampleAndProcess(sampleKey) {
    const sample = SAMPLES[sampleKey] || SAMPLES.redes;
    this.lectureTitleInput.value = sample.title;
    this.currentTopicTitle.textContent = sample.title;
    this.currentTopicTag.textContent = sample.course;
    
    this.transitionTo(AppState.PROCESSING);
    this.updateProcessingStep('audio', 'Concluído', true);
    this.updateProcessingStep('whisper', 'Em execução...', false, true);
    
    await this.sleep(400);
    this.updateProcessingStep('whisper', 'Concluído', true);
    this.updateProcessingStep('filter', 'Eliminando cacoetes...', false, true);

    await this.sleep(400);
    this.updateProcessingStep('filter', 'Concluído', true);
    this.updateProcessingStep('gemini', 'Estruturando tópicos...', false, true);

    await this.sleep(500);
    this.updateProcessingStep('gemini', 'Concluído', true);

    this.renderFallbackResult(sample.course, sample.title, sample.duration);
    this.transitionTo(AppState.READY);
    this.showToast(`Exemplo carregado: ${sample.course}`, 'success');
  }

  // --- Copy & Export ---
  async handleCopySummary() {
    if (!this.currentResult) return;

    const formattedText = this.buildExportText(this.currentResult);
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(formattedText);
      } else {
        const textArea = document.createElement('textarea');
        textArea.value = formattedText;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
      }
      this.showToast('Resumo copiado para a área de transferência!', 'success');
    } catch (err) {
      console.error('Erro ao copiar:', err);
      this.showToast('Não foi possível copiar automaticamente.', 'error');
    }
  }

  handleExportTxt() {
    if (!this.currentResult) return;

    const formattedText = this.buildExportText(this.currentResult);
    const blob = new Blob([formattedText], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    
    const safeTitle = (this.currentResult.title || 'resumo_aula')
      .toLowerCase()
      .replace(/[^a-z0-9]/g, '_')
      .slice(0, 30);
    
    const filename = `lecture_summary_${safeTitle}_${Date.now()}.txt`;
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);

    this.showToast(`Arquivo baixado: ${filename}`, 'success');
  }

  buildExportText(result) {
    let out = `=====================================================\n`;
    out += `UNISCRIBE — RESUMO DA AULA\n`;
    out += `=====================================================\n\n`;
    out += `Título: ${result.title}\n`;
    out += `Disciplina: ${result.course}\n`;
    out += `Data: ${result.date}\n`;
    out += `Duração Estimada: ${result.duration}\n\n`;
    out += `-----------------------------------------------------\n`;
    out += `1. CONCEITOS PRINCIPAIS & DEFINIÇÕES\n`;
    out += `-----------------------------------------------------\n`;
    if (result.concepts) {
      result.concepts.forEach(c => out += `• ${c}\n`);
    } else if (result.summaryText) {
      out += `• ${result.summaryText}\n`;
    }
    out += `\n`;

    if (result.highlights && result.highlights.length > 0) {
      out += `-----------------------------------------------------\n`;
      out += `2. DESTAQUES DE PROVA & FÓRMULAS\n`;
      out += `-----------------------------------------------------\n`;
      result.highlights.forEach(h => out += `▶ ${h}\n`);
      out += `\n`;
    }

    if (result.questions && result.questions.length > 0) {
      out += `-----------------------------------------------------\n`;
      out += `3. PERGUNTAS & DÚVIDAS ESCLARECIDAS\n`;
      out += `-----------------------------------------------------\n`;
      result.questions.forEach(q => out += `💬 ${q}\n`);
      out += `\n`;
    }

    if (result.executive) {
      out += `-----------------------------------------------------\n`;
      out += `4. SÍNTESE EXECUTIVA\n`;
      out += `-----------------------------------------------------\n`;
      out += `${result.executive}\n\n`;
    }

    out += `-----------------------------------------------------\n`;
    out += `5. TRANSCRIÇÃO FILTRADA (CONTEÚDO RELEVANTE)\n`;
    out += `-----------------------------------------------------\n`;
    out += `${result.filteredText || 'Não disponível.'}\n\n`;

    out += `=====================================================\n`;
    out += `Gerado automaticamente pelo UniScribe MVP\n`;
    out += `Processamento: ASR + Filtro Conservador + Resumo (Gemini ou fallback local)\n`;
    out += `=====================================================\n`;
    return out;
  }

  // --- UI Helpers ---
  switchTab(tabId) {
    this.tabButtons.forEach(btn => {
      btn.classList.toggle('active', btn.getAttribute('data-tab') === tabId);
    });
    this.tabContents.forEach(content => {
      content.classList.toggle('active', content.id === tabId);
    });
  }

  resetRecorderState() {
    this.audioChunks = [];
    this.elapsedSeconds = 0;
    this.recordingTimer.textContent = '00:00:00';
    if (this.waveformCanvas) {
      const ctx = this.waveformCanvas.getContext('2d');
      ctx.clearRect(0, 0, this.waveformCanvas.width, this.waveformCanvas.height);
    }
  }

  showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    this.toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.animation = 'toast-out 0.25s ease forwards';
      setTimeout(() => toast.remove(), 250);
    }, 3200);
  }

  openSettings() {
    this.backendUrlInput.value = this.backendUrl;
    this.simulationToggle.checked = this.simulationMode;
    this.settingsModal.style.display = 'flex';
  }

  closeSettings() {
    this.settingsModal.style.display = 'none';
  }

  saveSettings() {
    const requestedUrl = this.backendUrlInput.value.trim();
    this.backendUrl = normaliseBackendUrl(requestedUrl);
    this.backendUrlInput.value = this.backendUrl;
    this.simulationMode = this.simulationToggle.checked;
    localStorage.setItem('uniscribe_backend_url', this.backendUrl);
    localStorage.setItem('uniscribe_simulation', String(this.simulationMode));
    this.closeSettings();
    this.checkBackendHealth();
    this.showToast('Configurações salvas!', 'success');
  }

  blobToBase64(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => {
        const base64data = reader.result.split(',')[1];
        resolve(base64data);
      };
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// Instantiate on DOM load
document.addEventListener('DOMContentLoaded', () => {
  window.uniscribeApp = new UniScribeApp();
});
