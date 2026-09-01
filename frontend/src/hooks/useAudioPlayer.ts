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
  const nextPlayTime = useRef(0);
  const activeGeneration = useRef<number | null>(null);

  // Initialize AudioContext lazily to comply with browser autoplay policies
  const initAudioContext = () => {
    if (!audioContext.current) {
      audioContext.current = new window.AudioContext();
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
    
    if (!audioContext.current) return;
    
    isPlayingQueue.current = true;
    setIsPlaying(true);
    
    const buffer = audioQueue.current.shift()!;
    const source = audioContext.current.createBufferSource();
    source.buffer = buffer;
    source.connect(audioContext.current.destination);
    
    const currentTime = audioContext.current.currentTime;
    const playTime = Math.max(currentTime, nextPlayTime.current);
    
    source.start(playTime);
    nextPlayTime.current = playTime + buffer.duration;
    
    currentSource.current = source;
    
    source.onended = () => {
      // Check if we need to play next, small buffer
      if (audioQueue.current.length > 0) {
        playNextInQueue();
      } else {
        // Wait a bit to see if more chunks arrive
        setTimeout(() => {
          if (audioQueue.current.length === 0) {
            isPlayingQueue.current = false;
            setIsPlaying(false);
          } else {
            playNextInQueue();
          }
        }, 100);
      }
    };
  }, []);

  const playChunk = useCallback((base64Data: string, generationId: number, isFinal: boolean) => {
    if (activeGeneration.current !== generationId && activeGeneration.current !== null) {
      // If we receive a chunk for a new generation, clear previous queue
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
      
      ctx.decodeAudioData(bytes.buffer, (buffer) => {
        // Double check generation id hasn't changed while decoding
        if (activeGeneration.current !== generationId) return;
        
        audioQueue.current.push(buffer);
        
        if (!isPlayingQueue.current) {
          nextPlayTime.current = ctx.currentTime;
          playNextInQueue();
        }
      }, (e) => {
        console.error('Error decoding audio data', e);
      });
      
    } catch (e) {
      console.error('Error parsing audio base64', e);
    }
    
    if (isFinal) {
      // We know this is the last chunk for this generation
      // When queue empties, we reset generation tracking
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
    nextPlayTime.current = 0;
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
