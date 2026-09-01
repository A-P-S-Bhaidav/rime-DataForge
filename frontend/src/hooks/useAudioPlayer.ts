import { useState, useRef, useCallback, useEffect } from 'react';

export interface UseAudioPlayerReturn {
  isPlaying: boolean;
  playChunk: (base64Data: string, generationId: number, isFinal: boolean) => void;
  stop: () => void;
  currentGenerationId: number | null;
}

export function useAudioPlayer(): UseAudioPlayerReturn {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentGenerationId, setCurrentGenerationId] = useState<number | null>(null);
  
  const audioContext = useRef<AudioContext | null>(null);
  const audioQueue = useRef<AudioBuffer[]>([]);
  const isPlayingQueue = useRef(false);
  const currentSource = useRef<AudioBufferSourceNode | null>(null);
  const activeGeneration = useRef<number | null>(null);

  const initAudioContext = () => {
    if (!audioContext.current) {
      audioContext.current = new window.AudioContext({ sampleRate: 44100 });
    }
    if (audioContext.current.state === 'suspended') {
      audioContext.current.resume();
    }
    return audioContext.current;
  };

  const playNextInQueue = useCallback(() => {
    if (audioQueue.current.length === 0) {
      isPlayingQueue.current = false;
      setIsPlaying(false);
      return;
    }
    
    const ctx = audioContext.current;
    if (!ctx) return;
    
    isPlayingQueue.current = true;
    setIsPlaying(true);
    
    const buffer = audioQueue.current.shift()!;
    const source = ctx.createBufferSource();
    source.buffer = buffer;
    
    // Add a small gain to normalize volume
    const gainNode = ctx.createGain();
    gainNode.gain.value = 1.0;
    source.connect(gainNode);
    gainNode.connect(ctx.destination);
    
    source.start(0);
    currentSource.current = source;
    
    source.onended = () => {
      currentSource.current = null;
      if (audioQueue.current.length > 0) {
        playNextInQueue();
      } else {
        isPlayingQueue.current = false;
        setIsPlaying(false);
      }
    };
  }, []);

  const playChunk = useCallback((base64Data: string, generationId: number, _isFinal: boolean) => {
    // Skip empty data (final marker)
    if (!base64Data) return;

    if (activeGeneration.current !== generationId && activeGeneration.current !== null) {
      stop();
    }
    
    activeGeneration.current = generationId;
    setCurrentGenerationId(generationId);
    
    const ctx = initAudioContext();
    
    try {
      // Decode base64 to array buffer
      const binaryString = window.atob(base64Data);
      const len = binaryString.length;
      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }
      
      // Use a copy of the buffer (decodeAudioData detaches the original)
      const audioBuffer = bytes.buffer.slice(0);
      
      ctx.decodeAudioData(audioBuffer, (buffer) => {
        if (activeGeneration.current !== generationId) return;
        
        audioQueue.current.push(buffer);
        
        if (!isPlayingQueue.current) {
          playNextInQueue();
        }
      }, (e) => {
        console.error('Error decoding audio data:', e);
      });
      
    } catch (e) {
      console.error('Error parsing audio base64:', e);
    }
  }, [playNextInQueue]);

  const stop = useCallback(() => {
    if (currentSource.current) {
      try {
        currentSource.current.stop();
        currentSource.current.disconnect();
      } catch (e) {}
      currentSource.current = null;
    }
    
    audioQueue.current = [];
    isPlayingQueue.current = false;
    activeGeneration.current = null;
    setIsPlaying(false);
    setCurrentGenerationId(null);
  }, []);

  useEffect(() => {
    return () => {
      stop();
      if (audioContext.current) {
        audioContext.current.close();
      }
    };
  }, [stop]);

  return {
    isPlaying,
    playChunk,
    stop,
    currentGenerationId
  };
}
