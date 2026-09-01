import { useState, useCallback, useRef } from 'react';

export interface UseSpeechRecognitionReturn {
  transcript: string;
  interimTranscript: string;
  isListening: boolean;
  isSupported: boolean;
  startListening: () => void;
  stopListening: () => void;
  error: string | null;
}

export function useSpeechRecognition(): UseSpeechRecognitionReturn {
  const [transcript, setTranscript] = useState('');
  const [interimTranscript, setInterimTranscript] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const recognition = useRef<any>(null);
  const isListeningRef = useRef(false);

  const isSupported = typeof window !== 'undefined' && 
    ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window);

  const getRecognition = () => {
    if (recognition.current) return recognition.current;
    if (!isSupported) return null;

    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const rec = new SpeechRecognition();
    rec.continuous = false;   // Stop after one utterance — user clicks to start/stop
    rec.interimResults = true;
    rec.lang = 'en-US';
    rec.maxAlternatives = 1;

    rec.onresult = (event: any) => {
      let finalText = '';
      let interimText = '';
      
      for (let i = 0; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) {
          finalText += result[0].transcript;
        } else {
          interimText += result[0].transcript;
        }
      }
      
      if (finalText) {
        setTranscript(finalText);
        setInterimTranscript('');
      } else {
        setInterimTranscript(interimText);
      }
    };

    rec.onerror = (event: any) => {
      console.error('Speech recognition error:', event.error);
      if (event.error === 'not-allowed') {
        setError('Microphone access denied. Please allow microphone permission.');
      } else if (event.error === 'no-speech') {
        setError('No speech detected. Try again.');
      } else {
        setError(event.error);
      }
      isListeningRef.current = false;
      setIsListening(false);
    };

    rec.onend = () => {
      // Only auto-set state, don't restart
      isListeningRef.current = false;
      setIsListening(false);
    };

    recognition.current = rec;
    return rec;
  };

  const startListening = useCallback(() => {
    const rec = getRecognition();
    if (!rec) return;
    
    setError(null);
    setTranscript('');
    setInterimTranscript('');
    
    try {
      rec.start();
      isListeningRef.current = true;
      setIsListening(true);
    } catch (e: any) {
      // If already started, stop and restart
      if (e.message?.includes('already started')) {
        rec.stop();
        setTimeout(() => {
          try {
            rec.start();
            isListeningRef.current = true;
            setIsListening(true);
          } catch (_) {
            isListeningRef.current = false;
            setIsListening(false);
          }
        }, 100);
      } else {
        console.error('Could not start recognition', e);
        isListeningRef.current = false;
        setIsListening(false);
      }
    }
  }, []);

  const stopListening = useCallback(() => {
    isListeningRef.current = false;
    setIsListening(false);
    try {
      recognition.current?.stop();
    } catch (_) {}
  }, []);

  return {
    transcript,
    interimTranscript,
    isListening,
    isSupported,
    startListening,
    stopListening,
    error
  };
}
