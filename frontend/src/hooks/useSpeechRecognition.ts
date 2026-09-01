import { useState, useCallback, useRef, useEffect } from 'react';

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
  
  const recognitionRef = useRef<any>(null);
  const isListeningRef = useRef(false);
  const shouldRestart = useRef(false);

  const isSupported = typeof window !== 'undefined' && 
    ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window);

  // Initialize recognition once on mount
  useEffect(() => {
    if (!isSupported) return;

    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const rec = new SpeechRecognition();
    rec.continuous = true;
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
        setTranscript(finalText.trim());
        setInterimTranscript('');
      }
      if (interimText) {
        setInterimTranscript(interimText);
      }
    };

    rec.onerror = (event: any) => {
      console.error('Speech recognition error:', event.error);
      if (event.error === 'not-allowed') {
        setError('Microphone access denied. Please allow microphone in browser settings.');
        shouldRestart.current = false;
        isListeningRef.current = false;
        setIsListening(false);
      } else if (event.error === 'no-speech') {
        // This is normal — just means silence was detected
        // Don't stop, let it keep listening
      } else if (event.error === 'aborted') {
        // User or code stopped it — do nothing
      } else {
        setError(`Speech error: ${event.error}`);
        shouldRestart.current = false;
        isListeningRef.current = false;
        setIsListening(false);
      }
    };

    rec.onend = () => {
      // Browser may stop recognition automatically (e.g., after silence)
      // If we're still supposed to be listening, restart it
      if (shouldRestart.current && isListeningRef.current) {
        try {
          setTimeout(() => {
            if (shouldRestart.current && isListeningRef.current) {
              rec.start();
            }
          }, 50);
        } catch (e) {
          shouldRestart.current = false;
          isListeningRef.current = false;
          setIsListening(false);
        }
      } else {
        isListeningRef.current = false;
        setIsListening(false);
      }
    };

    recognitionRef.current = rec;

    return () => {
      shouldRestart.current = false;
      isListeningRef.current = false;
      try { rec.stop(); } catch (_) {}
    };
  }, [isSupported]);

  const startListening = useCallback(() => {
    if (!recognitionRef.current) return;
    
    setError(null);
    setTranscript('');
    setInterimTranscript('');
    
    shouldRestart.current = true;
    isListeningRef.current = true;
    setIsListening(true);

    try {
      recognitionRef.current.start();
    } catch (e: any) {
      // If already started, stop first then restart
      try {
        recognitionRef.current.stop();
      } catch (_) {}
      setTimeout(() => {
        try {
          recognitionRef.current?.start();
        } catch (_) {
          shouldRestart.current = false;
          isListeningRef.current = false;
          setIsListening(false);
        }
      }, 100);
    }
  }, []);

  const stopListening = useCallback(() => {
    shouldRestart.current = false;
    isListeningRef.current = false;
    setIsListening(false);
    try {
      recognitionRef.current?.stop();
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
