import { useEffect, useRef, useCallback, useState } from 'react';
import { getSupabase } from '../services/supabase';
import type { NavigateFn } from '../App';

const LETTERS = ['F', 'U', 'T', 'U', 'R', 'E', 'S'];
const DELAYS = [0, 70, 140, 210, 280, 350, 420];

interface Props { navigate: NavigateFn; }

export default function Splash({ navigate }: Props) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const hasAnimatedRef = useRef(false);
  const soundPlayedRef = useRef(false);
  const [visibleLetters, setVisibleLetters] = useState<boolean[]>(new Array(7).fill(false));
  const [showMotto, setShowMotto] = useState(false);
  const [showTapHint, setShowTapHint] = useState(false);
  const [breathing, setBreathing] = useState(false);
  const [scanAnimate, setScanAnimate] = useState(false);
  const [dotAnimate, setDotAnimate] = useState(false);
  const [fadeOut, setFadeOut] = useState(false);
  const [particles, setParticles] = useState<{ id: number; left: string; top: string; delay: string }[]>([]);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    getSupabase().then((sb) => {
      sb.auth.getSession().then((s) => {
        if (s.data.session) {
          navigate('dashboard');
        } else {
          setReady(true);
        }
      });
    });
  }, [navigate]);

  useEffect(() => {
    const audio = new Audio('/cashout.mp3');
    audio.volume = 0.65;
    audio.preload = 'auto';
    audioRef.current = audio;
    return () => { audio.pause(); audio.src = ''; };
  }, []);

  useEffect(() => {
    if (!ready || hasAnimatedRef.current) return;
    hasAnimatedRef.current = true;

    DELAYS.forEach((delay, i) => {
      setTimeout(() => {
        setVisibleLetters((prev) => {
          const next = [...prev];
          next[i] = true;
          return next;
        });
      }, delay + 200);
    });

    setTimeout(() => setScanAnimate(true), 700);
    setTimeout(() => setDotAnimate(true), 1200);
    setTimeout(() => {
      setParticles(
        Array.from({ length: 8 }, (_, i) => ({
          id: i,
          left: `${20 + Math.random() * 60}%`,
          top: `${35 + Math.random() * 30}%`,
          delay: `${1.2 + Math.random() * 1.5}s`,
        }))
      );
    }, 700);
    setTimeout(() => setShowMotto(true), 1100);
    setTimeout(() => setBreathing(true), 1200);
    setTimeout(() => setShowTapHint(true), 2000);
  }, [ready]);

  const handleTap = useCallback(() => {
    if (!hasAnimatedRef.current || soundPlayedRef.current) return;
    soundPlayedRef.current = true;
    setShowTapHint(false);

    const audio = audioRef.current;
    if (audio) {
      audio.currentTime = 0;
      audio.play().catch(() => {});
    }

    setFadeOut(true);
    setTimeout(() => navigate('login'), 900);
  }, [navigate]);

  if (!ready) return null;

  return (
    <div className={`splash-root${fadeOut ? ' fade-out' : ''}`} onClick={handleTap} onTouchStart={handleTap}>
      <style>{`
        .splash-root {
          position: fixed; inset: 0;
          display: flex; flex-direction: column;
          align-items: center; justify-content: center;
          background: #000 radial-gradient(circle at 50% 40%, rgba(255,255,255,0.06) 0%, transparent 80%);
          cursor: pointer; overflow: hidden;
          transition: opacity 0.6s ease-out; z-index: 9999;
        }
        .splash-root.fade-out { opacity: 0; pointer-events: none; }
        .scan-line {
          position: absolute; top: 38%; left: 0; width: 100%; height: 1px;
          background: linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.6) 50%, transparent 100%);
          transform: translateY(-40px); opacity: 0; pointer-events: none;
        }
        .scan-line.animate { animation: scanSweep 0.8s ease-out 0.6s forwards; }
        @keyframes scanSweep {
          0% { transform: translateY(-40px); opacity: 0; }
          20% { opacity: 0.6; }
          100% { transform: translateY(25px); opacity: 0; }
        }
        .micro-dot { position: absolute; width: 3px; height: 3px; background: #fff; border-radius: 50%; opacity: 0; pointer-events: none; }
        .micro-dot.left-dot { top: 38%; left: 25%; }
        .micro-dot.right-dot { top: 38%; right: 25%; }
        .micro-dot.left-dot.animate { animation: dotFlicker 0.6s ease-out 1s forwards; }
        .micro-dot.right-dot.animate { animation: dotFlicker 0.6s ease-out 1.1s forwards; }
        @keyframes dotFlicker {
          0% { transform: scale(0.5); opacity: 0; }
          50% { transform: scale(1.2); opacity: 1; }
          100% { transform: scale(0); opacity: 0; }
        }
        .title-wrapper { position: relative; z-index: 2; display: flex; align-items: center; justify-content: center; }
        .futures-title {
          font-family: "Dancing Script", cursive; font-weight: 700;
          font-size: clamp(3.2rem, 16vw, 7.5rem); color: #fff;
          letter-spacing: 0.02em; text-shadow: 0 0 12px rgba(255,255,255,0.3);
          display: flex; gap: 0; user-select: none;
        }
        .futures-title.breathing { animation: breathe 5s ease-in-out infinite; }
        @keyframes breathe {
          0%, 100% { transform: scale(1); text-shadow: 0 0 12px rgba(255,255,255,0.3); }
          50% { transform: scale(1.008); text-shadow: 0 0 20px rgba(255,255,255,0.45), 0 0 40px rgba(100,180,255,0.15); }
        }
        .futures-letter { display: inline-block; opacity: 0; transform: scale(0.85) translateY(10px); filter: blur(2px); will-change: opacity, transform, filter; }
        .futures-letter.visible {
          opacity: 1; transform: scale(1) translateY(0); filter: blur(0);
          transition: opacity 0.28s cubic-bezier(0.25, 0.46, 0.45, 0.94),
                      transform 0.28s cubic-bezier(0.25, 0.46, 0.45, 0.94),
                      filter 0.28s cubic-bezier(0.25, 0.46, 0.45, 0.94);
        }
        .motto {
          margin-top: 2.5rem; font-family: "Inter", sans-serif; font-size: 1rem;
          letter-spacing: 0.2em; color: #bbddff; background: rgba(255,255,255,0.03);
          border: 1px solid rgba(100,180,255,0.3); border-radius: 60px;
          padding: 0.5rem 1.2rem; backdrop-filter: blur(8px);
          opacity: 0; transform: translateY(20px);
          transition: opacity 0.6s ease-out, transform 0.6s ease-out;
          user-select: none;
        }
        .motto.visible { opacity: 1; transform: translateY(0); }
        .tap-hint {
          position: absolute; bottom: 2.5rem; font-family: "Inter", sans-serif;
          font-size: 0.75rem; letter-spacing: 0.15em; color: rgba(255,255,255,0.2);
          opacity: 0; transition: opacity 1s ease-out; user-select: none;
          animation: pulseHint 3s ease-in-out infinite;
        }
        .tap-hint.visible { opacity: 1; }
        @keyframes pulseHint { 0%, 100% { opacity: 0.2; } 50% { opacity: 0.5; } }
        .particle { position: absolute; width: 2px; height: 2px; background: rgba(255,255,255,0.15); border-radius: 50%; pointer-events: none; opacity: 0; }
        .particle.animate { animation: particleFloat 3s ease-out forwards; }
        @keyframes particleFloat {
          0% { opacity: 0; transform: translateY(0) scale(0); }
          20% { opacity: 0.6; transform: translateY(-10px) scale(1); }
          100% { opacity: 0; transform: translateY(-40px) scale(0.3); }
        }
        @media (max-width: 480px) {
          .motto { font-size: 0.75rem; margin-top: 2rem; padding: 0.4rem 1rem; }
          .tap-hint { font-size: 0.65rem; bottom: 1.5rem; }
        }
        @media (prefers-reduced-motion: reduce) {
          .futures-letter, .motto, .scan-line, .micro-dot, .particle {
            animation: none !important; transition: opacity 0.3s ease-out !important;
          }
          .futures-letter.visible { opacity: 1 !important; transform: none !important; filter: none !important; }
          .motto.visible { opacity: 1 !important; transform: none !important; }
          .futures-title.breathing { animation: none !important; }
        }
      `}</style>

      <div className={`scan-line${scanAnimate ? ' animate' : ''}`} />
      <div className={`micro-dot left-dot${dotAnimate ? ' animate' : ''}`} />
      <div className={`micro-dot right-dot${dotAnimate ? ' animate' : ''}`} />
      {particles.map((p) => (
        <div key={p.id} className="particle animate" style={{ left: p.left, top: p.top, animationDelay: p.delay }} />
      ))}
      <div className="title-wrapper">
        <h1 className={`futures-title${breathing ? ' breathing' : ''}`} aria-label="FUTURES">
          {LETTERS.map((letter, i) => (
            <span key={i} className={`futures-letter${visibleLetters[i] ? ' visible' : ''}`}>{letter}</span>
          ))}
        </h1>
      </div>
      <p className={`motto${showMotto ? ' visible' : ''}`}>PRICE IS THE ONLY INDICATOR</p>
      <p className={`tap-hint${showTapHint ? ' visible' : ''}`}>TAP TO CONTINUE</p>
    </div>
  );
}
