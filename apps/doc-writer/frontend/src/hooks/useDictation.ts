import { useCallback, useEffect, useRef, useState } from "react";

import { sessionsApi } from "../lib/api";

export type DictationState = "idle" | "recording" | "transcribing";

function pcm16ToBase64(input: Float32Array): string {
  const pcm = new Int16Array(input.length);
  for (let index = 0; index < input.length; index += 1) {
    const sample = Math.max(-1, Math.min(1, input[index] ?? 0));
    pcm[index] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
  }
  const bytes = new Uint8Array(pcm.buffer);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

/**
 * Dictee vocale live : PCM16 navigateur -> WebSocket Voxtral Realtime.
 */
export function useDictation(onText: (text: string, isFirstDelta: boolean) => void) {
  const [state, setState] = useState<DictationState>("idle");
  const [error, setError] = useState<string | null>(null);
  const isFirstDeltaRef = useRef(true);
  const socketRef = useRef<WebSocket | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const silentGainRef = useRef<GainNode | null>(null);

  const releaseAudio = useCallback(() => {
    processorRef.current?.disconnect();
    sourceRef.current?.disconnect();
    silentGainRef.current?.disconnect();
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    void audioContextRef.current?.close();
    processorRef.current = null;
    sourceRef.current = null;
    silentGainRef.current = null;
    mediaStreamRef.current = null;
    audioContextRef.current = null;
  }, []);

  const closeSocket = useCallback(() => {
    const socket = socketRef.current;
    socketRef.current = null;
    if (socket && socket.readyState < WebSocket.CLOSING) socket.close(1000);
  }, []);

  useEffect(() => () => {
    releaseAudio();
    closeSocket();
  }, [closeSocket, releaseAudio]);

  const start = useCallback(async () => {
    setError(null);
    isFirstDeltaRef.current = true;
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Micro non disponible dans ce navigateur.");
      return;
    }
    setState("transcribing");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
      mediaStreamRef.current = stream;
      const session = await sessionsApi.realtimeTranscriptionToken();
      if (!session.enabled) throw new Error("LLM desactive.");

      const audioContext = new AudioContext({ sampleRate: 16_000 });
      audioContextRef.current = audioContext;
      const source = audioContext.createMediaStreamSource(stream);
      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      const silentGain = audioContext.createGain();
      silentGain.gain.value = 0;
      sourceRef.current = source;
      processorRef.current = processor;
      silentGainRef.current = silentGain;

      const socket = new WebSocket(session.websocket_url, ["realtime", session.token]);
      socketRef.current = socket;
      socket.onmessage = (message) => {
        let event: { type?: string; text?: string; error?: { message?: string } };
        try {
          event = JSON.parse(String(message.data)) as typeof event;
        } catch {
          return;
        }
        if (event.type === "session.created") {
          socket.send(JSON.stringify({
            type: "session.update",
            session: {
              audio_format: {
                encoding: "pcm_s16le",
                sample_rate: audioContext.sampleRate,
              },
            },
          }));
          processor.onaudioprocess = (audioEvent) => {
            if (socket.readyState !== WebSocket.OPEN) return;
            socket.send(JSON.stringify({
              type: "input_audio.append",
              audio: pcm16ToBase64(audioEvent.inputBuffer.getChannelData(0)),
            }));
          };
          source.connect(processor);
          processor.connect(silentGain);
          silentGain.connect(audioContext.destination);
          setState("recording");
        } else if (event.type === "transcription.text.delta" && event.text) {
          onText(event.text, isFirstDeltaRef.current);
          isFirstDeltaRef.current = false;
        } else if (event.type === "transcription.done") {
          releaseAudio();
          closeSocket();
          setState("idle");
        } else if (event.type === "error") {
          setError(event.error?.message || "Erreur Voxtral Realtime.");
          releaseAudio();
          closeSocket();
          setState("idle");
        }
      };
      socket.onerror = () => {
        setError("Connexion Voxtral Realtime impossible.");
        releaseAudio();
        closeSocket();
        setState("idle");
      };
      socket.onclose = (closeEvent) => {
        if (socketRef.current !== socket) return;
        socketRef.current = null;
        releaseAudio();
        if (closeEvent.code !== 1000) {
          setError("Connexion Voxtral Realtime interrompue.");
        }
        setState("idle");
      };
    } catch (caught) {
      releaseAudio();
      closeSocket();
      setError(caught instanceof Error ? caught.message : "Acces micro refuse.");
      setState("idle");
    }
  }, [closeSocket, onText, releaseAudio]);

  const stop = useCallback(() => {
    const socket = socketRef.current;
    releaseAudio();
    if (socket?.readyState === WebSocket.OPEN) {
      setState("transcribing");
      socket.send(JSON.stringify({ type: "input_audio.flush" }));
      socket.send(JSON.stringify({ type: "input_audio.end" }));
    } else {
      closeSocket();
      setState("idle");
    }
  }, [closeSocket, releaseAudio]);

  const toggle = useCallback(() => {
    if (state === "recording") stop();
    else if (state === "idle") void start();
  }, [state, start, stop]);

  return { state, error, toggle };
}
