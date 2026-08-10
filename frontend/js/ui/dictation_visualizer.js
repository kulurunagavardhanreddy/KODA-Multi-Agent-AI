// --- KODA Dictation & Voice Visualizer UI Module ---

let dictationRecognition = null;
let isDictating = false;
let dictationBaseText = "";

window.toggleDictation = function () {
  const micBtn = document.getElementById("mic-btn");
  const inputField = document.getElementById("input");

  if (isDictating) {
    if (dictationRecognition) dictationRecognition.stop();
    return;
  }

  if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
    alert("Speech recognition is not supported in this browser. Try using Chrome or Edge.");
    return;
  }

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  dictationRecognition = new SpeechRecognition();
  dictationRecognition.continuous = false;
  dictationRecognition.interimResults = true;

  // Apply custom accent/voice!
  if (selectedVoiceURI) {
    const voices = window.speechSynthesis.getVoices();
    const chosenVoice = voices.find(v => v.voiceURI === selectedVoiceURI);
  }

  // Apply the explicitly chosen spoken language to the microphone!
  dictationRecognition.lang = micLang;

  dictationRecognition.onstart = function () {
    isDictating = true;
    dictationBaseText = inputField.value;
    micBtn.innerHTML = micRecordingSvg;
    document.getElementById("dictation-visualizer").style.display = "flex";
    inputField.style.paddingLeft = "85px"; // Push text to the right so it doesn't overlap the wave
    inputField.placeholder = "Listening...";
  };

  dictationRecognition.onresult = function (event) {
    let currentTranscript = '';
    for (let i = event.resultIndex; i < event.results.length; ++i) {
      currentTranscript += event.results[i][0].transcript;
    }
    if (currentTranscript) {
      const space = (dictationBaseText && !dictationBaseText.endsWith(' ') && !dictationBaseText.endsWith('\n')) ? " " : "";
      inputField.value = dictationBaseText + space + currentTranscript;
      inputField.style.height = 'auto';
      inputField.style.height = (inputField.scrollHeight) + 'px';
      toggleSendButtonState();
    }
  };

  dictationRecognition.onend = function () {
    isDictating = false;
    micBtn.innerHTML = micSvg;
    document.getElementById("dictation-visualizer").style.display = "none";
    inputField.style.paddingLeft = ""; // Revert to CSS default
    inputField.placeholder = "Type a message...";
    toggleSendButtonState();
  };

  dictationRecognition.start();
};

// --- Real-Time Audio Visualizer Logic ---
let audioContext = null;
let analyser = null;
let microphoneStream = null;
let visualizerFrameId = null;

async function startAudioVisualizer() {
  try {
    microphoneStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    analyser = audioContext.createAnalyser();
    const source = audioContext.createMediaStreamSource(microphoneStream);
    source.connect(analyser);
    analyser.fftSize = 256;
    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    const bars = document.querySelectorAll("#voice-visualizer .bar");

    function renderFrame() {
      if (!analyser) return;
      analyser.getByteFrequencyData(dataArray);
      const bins = [2, 4, 6, 8, 10]; // Sample specific frequency channels
      for (let i = 0; i < 5; i++) {
        const value = dataArray[bins[i]] || 0;
        const height = 12 + (value / 255) * 58; // Base 12px, peaks at ~70px
        if (bars[i]) {
          bars[i].style.height = `${height}px`;
          bars[i].style.animation = "none"; // Override the CSS loop!
        }
      }
      visualizerFrameId = requestAnimationFrame(renderFrame);
    }
    renderFrame();
  } catch (err) { console.error("Audio visualizer error:", err); }
}

function stopAudioVisualizer() {
  if (visualizerFrameId) cancelAnimationFrame(visualizerFrameId);
  if (audioContext) audioContext.close();
  if (microphoneStream) microphoneStream.getTracks().forEach(t => t.stop());
  audioContext = analyser = microphoneStream = visualizerFrameId = null;
  document.querySelectorAll("#voice-visualizer .bar").forEach(bar => { bar.style.height = ""; bar.style.animation = ""; });
}

// --- Advanced Voice Mode (Continuous Conversation Loop) ---
let voiceRecognition = null;
let isVoiceMode = false;

window.toggleVoiceMode = function () {
  const modal = document.getElementById("voice-modal");
  if (isVoiceMode) {
    closeVoiceMode();
    return;
  }
  isVoiceMode = true;
  modal.style.display = "flex";
  startListening();
};

window.closeVoiceMode = function () {
  isVoiceMode = false;
  document.getElementById("voice-modal").style.display = "none";
  if (voiceRecognition) voiceRecognition.stop();
  stopAudioVisualizer();
  stopAllAudio();
};

function startListening() {
  if (!isVoiceMode) return;

  const voiceText = document.getElementById("voice-text");
  const visualizer = document.getElementById("voice-visualizer");
  const inputField = document.getElementById("input");

  if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
    alert("Speech recognition is not supported in this browser. Try using Chrome or Edge.");
    closeVoiceMode();
    return;
  }

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  voiceRecognition = new SpeechRecognition();
  voiceRecognition.continuous = false;
  voiceRecognition.interimResults = true;

  // Apply custom accent/voice to Speech Recognition!
  if (selectedVoiceURI) {
    const voices = window.speechSynthesis.getVoices();
    const chosenVoice = voices.find(v => v.voiceURI === selectedVoiceURI);
  }

  // Apply the explicitly chosen spoken language to the microphone!
  voiceRecognition.lang = micLang;

  voiceRecognition.onstart = function () {
    visualizer.className = "listening";
    startAudioVisualizer(); // Intercept animation with real-time mic volume!
    voiceText.innerText = "Listening...";
  };

  voiceRecognition.onresult = function (event) {
    let finalTranscript = '';
    let interimTranscript = '';
    for (let i = event.resultIndex; i < event.results.length; ++i) {
      if (event.results[i].isFinal) {
        finalTranscript += event.results[i][0].transcript;
      } else {
        interimTranscript += event.results[i][0].transcript;
      }
    }
    const displayTxt = finalTranscript || interimTranscript;
    if (displayTxt) {
      voiceText.innerText = displayTxt;
      inputField.value = displayTxt;
    }
  };

  voiceRecognition.onend = function () {
    stopAudioVisualizer(); // Stop intercepting so CSS "thinking" loop takes over
    if (!isVoiceMode) return;
    if (inputField.value.trim() !== "") {
      visualizer.className = "thinking";
      voiceText.innerText = "Thinking...";
      autoReadResponse = true;
      sendMessage(); // Triggers the AI backend!
    } else {
      startListening(); // Restart if it timed out with no audio
    }
  };

  voiceRecognition.start();
}
