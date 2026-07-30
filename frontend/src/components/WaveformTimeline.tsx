import { useRef, useEffect, useCallback, useState } from 'react';
import { useEditorStore } from '../store/editorStore';
import { ZoomIn, ZoomOut, AlertTriangle, LocateFixed } from 'lucide-react';
import { getPlaybackTimeState, getPlayableSeekTime } from '../utils/playback';

export default function WaveformTimeline() {
  const waveCanvasRef = useRef<HTMLCanvasElement>(null);
  const headCanvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [audioError, setAudioError] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [waveformRevision, setWaveformRevision] = useState(0);
  const [waveformLoading, setWaveformLoading] = useState(false);
  const [followPlayhead, setFollowPlayhead] = useState(true);

  const videoPath = useEditorStore((s) => s.videoPath);
  const duration = useEditorStore((s) => s.duration);
  const backendUrl = useEditorStore((s) => s.backendUrl);
  const words = useEditorStore((s) => s.words);
  const deletedRanges = useEditorStore((s) => s.deletedRanges);
  const editOperations = useEditorStore((s) => s.editOperations);
  const selectedWordIndices = useEditorStore((s) => s.selectedWordIndices);
  const previewCuts = useEditorStore((s) => s.previewCuts);
  const currentTime = useEditorStore((s) => s.currentTime);
  const requestSeek = useEditorStore((s) => s.requestSeek);
  const setSelectedWordIndices = useEditorStore((s) => s.setSelectedWordIndices);

  const waveformPeaksRef = useRef<Array<[number, number]>>([]);
  const waveformDurationRef = useRef(0);
  const rafRef = useRef(0);
  const currentTimeRef = useRef(0);
  const dragStartTimeRef = useRef<number | null>(null);
  const dragMovedRef = useRef(false);
  const manualScrollPauseUntilRef = useRef(0);
  const playbackState = getPlaybackTimeState(currentTime, duration, deletedRanges, previewCuts);

  useEffect(() => {
    currentTimeRef.current = currentTime;
  }, [currentTime]);

  const drawStaticWaveform = useCallback(() => {
    const canvas = waveCanvasRef.current;
    const peaks = waveformPeaksRef.current;
    const timelineDuration = waveformDurationRef.current || duration;
    if (!canvas || timelineDuration <= 0) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const width = rect.width;
    const height = rect.height;
    ctx.clearRect(0, 0, width, height);
    const rulerHeight = 18;
    const eventLaneHeight = 38;
    const eventLaneTop = height - eventLaneHeight;
    const markerLaneTop = eventLaneTop + 20;
    const waveformTop = rulerHeight + 5;
    const waveformHeight = Math.max(24, eventLaneTop - waveformTop - 5);
    const waveformMid = waveformTop + waveformHeight / 2;

    ctx.strokeStyle = '#252a27';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, rulerHeight + 0.5);
    ctx.lineTo(width, rulerHeight + 0.5);
    ctx.moveTo(0, eventLaneTop + 0.5);
    ctx.lineTo(width, eventLaneTop + 0.5);
    ctx.moveTo(0, markerLaneTop + 0.5);
    ctx.lineTo(width, markerLaneTop + 0.5);
    ctx.stroke();

    const tickCount = Math.max(4, Math.min(12, Math.floor(width / 120)));
    ctx.font = '9px SFMono-Regular, Cascadia Mono, monospace';
    ctx.textBaseline = 'top';
    ctx.fillStyle = '#7d867f';
    ctx.strokeStyle = '#353b37';
    ctx.beginPath();
    for (let tick = 0; tick <= tickCount; tick++) {
      const x = (tick / tickCount) * width;
      const tickTime = (tick / tickCount) * timelineDuration;
      ctx.moveTo(x, rulerHeight - 5);
      ctx.lineTo(x, rulerHeight);
      ctx.fillText(formatTimelineTime(tickTime), Math.min(width - 34, x + 3), 2);
    }
    ctx.stroke();

    for (const range of deletedRanges) {
      const x1 = (range.start / timelineDuration) * width;
      const x2 = (range.end / timelineDuration) * width;
      ctx.fillStyle = 'rgba(255, 113, 109, 0.16)';
      ctx.fillRect(x1, waveformTop, x2 - x1, waveformHeight);
      ctx.fillStyle = 'rgba(255, 113, 109, 0.7)';
      ctx.fillRect(x1, eventLaneTop + 5, Math.max(2, x2 - x1), 8);
    }

    for (const operation of editOperations) {
      const x1 = (operation.start / timelineDuration) * width;
      const x2 = (operation.end / timelineDuration) * width;
      ctx.fillStyle =
        operation.kind === 'mute'
          ? 'rgba(166, 174, 168, 0.18)'
          : operation.kind === 'bleep'
            ? 'rgba(255, 113, 109, 0.28)'
          : operation.kind === 'room-tone'
            ? 'rgba(231, 189, 99, 0.20)'
          : operation.kind === 'caption-only'
            ? 'rgba(148, 163, 184, 0.18)'
            : 'rgba(113, 217, 176, 0.13)';
      ctx.fillRect(x1, eventLaneTop + 5, Math.max(2, x2 - x1), 8);
    }

    if (selectedWordIndices.length > 0 && words.length > 0) {
      const selectedRanges = getSelectedTimeRanges(words, selectedWordIndices);
      for (const range of selectedRanges) {
        const x1 = (range.start / timelineDuration) * width;
        const x2 = (range.end / timelineDuration) * width;
        ctx.fillStyle = 'rgba(113, 217, 176, 0.28)';
        ctx.fillRect(x1, waveformTop, Math.max(2, x2 - x1), waveformHeight);
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.45)';
        ctx.lineWidth = 1;
        ctx.strokeRect(x1, waveformTop + 0.5, Math.max(2, x2 - x1), waveformHeight - 1);
        ctx.fillStyle = '#71d9b0';
        ctx.fillRect(x1, eventLaneTop + 5, Math.max(2, x2 - x1), 8);
        ctx.beginPath();
        ctx.arc(x1, markerLaneTop + 9, 3, 0, Math.PI * 2);
        ctx.arc(x2, markerLaneTop + 9, 3, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    for (const word of words) {
      if (word.confidence >= 0.65) continue;
      const x = (word.start / timelineDuration) * width;
      ctx.fillStyle = '#ff716d';
      ctx.beginPath();
      ctx.moveTo(x, markerLaneTop + 4);
      ctx.lineTo(x + 4, markerLaneTop + 9);
      ctx.lineTo(x, markerLaneTop + 14);
      ctx.lineTo(x - 4, markerLaneTop + 9);
      ctx.closePath();
      ctx.fill();
    }

    ctx.beginPath();
    ctx.strokeStyle = '#69716b';
    ctx.lineWidth = 1;

    if (peaks.length === 0) {
      ctx.moveTo(0, waveformMid);
      ctx.lineTo(width, waveformMid);
      ctx.stroke();

      ctx.beginPath();
      ctx.strokeStyle = '#2b302d';
      for (let tick = 0; tick <= tickCount; tick++) {
        const x = (tick / tickCount) * width;
        ctx.moveTo(x, waveformTop + waveformHeight * 0.25);
        ctx.lineTo(x, waveformTop + waveformHeight * 0.75);
      }
      ctx.stroke();
      return;
    }

    for (let index = 0; index < peaks.length; index++) {
      const x = peaks.length === 1 ? 0 : (index / (peaks.length - 1)) * width;
      const [minimum, maximum] = peaks[index];
      const yMin = waveformMid + minimum * waveformHeight * 0.46;
      const yMax = waveformMid + maximum * waveformHeight * 0.46;
      ctx.moveTo(x, yMin);
      ctx.lineTo(x, yMax);
    }
    ctx.stroke();
  }, [deletedRanges, duration, editOperations, selectedWordIndices, words]);

  useEffect(() => {
    if (!videoPath) return;
    let canceled = false;
    const controller = new AbortController();

    setAudioError(null);
    setWaveformLoading(true);
    waveformPeaksRef.current = [];
    waveformDurationRef.current = 0;
    setWaveformRevision((revision) => revision + 1);

    const loadAudio = async () => {
      try {
        const query = new URLSearchParams({
          file_path: videoPath,
          points: '6000',
        });
        const response = await fetch(`${backendUrl}/audio/waveform?${query.toString()}`, {
          signal: controller.signal,
        });
        if (!response.ok) {
          let detail = response.statusText;
          try {
            const body = await response.json();
            detail = body.detail || detail;
          } catch {
            // Keep the HTTP status text for non-JSON failures.
          }
          throw new Error(detail);
        }
        const waveform = (await response.json()) as {
          duration: number;
          peaks: Array<[number, number]>;
        };
        if (canceled) return;
        waveformPeaksRef.current = Array.isArray(waveform.peaks) ? waveform.peaks : [];
        waveformDurationRef.current = Number.isFinite(waveform.duration) ? waveform.duration : 0;
        setWaveformRevision((revision) => revision + 1);
      } catch (err) {
        if (canceled || (err instanceof DOMException && err.name === 'AbortError')) return;
        console.warn('Could not build waveform:', err);
        waveformPeaksRef.current = [];
        waveformDurationRef.current = 0;
        setAudioError('Форма волны недоступна — монтаж и расшифровка продолжают работать');
        setWaveformRevision((revision) => revision + 1);
      } finally {
        if (!canceled) setWaveformLoading(false);
      }
    };

    loadAudio();

    return () => {
      canceled = true;
      controller.abort();
    };
  }, [backendUrl, videoPath]);

  // Redraw static layer when deletedRanges change
  useEffect(() => {
    drawStaticWaveform();
  }, [drawStaticWaveform, waveformRevision]);

  useEffect(() => {
    drawStaticWaveform();
  }, [drawStaticWaveform, zoom]);

  // Lightweight RAF loop for playhead only -- reads store time from a ref,
  // never triggers React re-renders
  useEffect(() => {
    const headCanvas = headCanvasRef.current;
    const waveCanvas = waveCanvasRef.current;
    if (!headCanvas || !waveCanvas) return;

    const tick = () => {
      const ctx = headCanvas.getContext('2d');
      if (!ctx) { rafRef.current = requestAnimationFrame(tick); return; }

      const dur = waveformDurationRef.current || duration;

      const dpr = window.devicePixelRatio || 1;
      const rect = headCanvas.getBoundingClientRect();
      if (headCanvas.width !== waveCanvas.width || headCanvas.height !== waveCanvas.height) {
        headCanvas.width = rect.width * dpr;
        headCanvas.height = rect.height * dpr;
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      const width = rect.width;
      const height = rect.height;
      ctx.clearRect(0, 0, width, height);

      if (dur > 0) {
        const px = (currentTimeRef.current / dur) * width;
        ctx.beginPath();
        ctx.strokeStyle = '#71d9b0';
        ctx.lineWidth = 2;
        ctx.moveTo(px, 0);
        ctx.lineTo(px, height);
        ctx.stroke();
      }

      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [videoPath, duration]);

  useEffect(() => {
    const observer = new ResizeObserver(() => {
      drawStaticWaveform();
    });
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [drawStaticWaveform]);

  useEffect(() => {
    if (!followPlayhead || dragStartTimeRef.current !== null) return;
    if (Date.now() < manualScrollPauseUntilRef.current) return;
    const container = containerRef.current?.querySelector('[data-timeline-scroll="true"]');
    const canvas = headCanvasRef.current;
    if (!(container instanceof HTMLDivElement) || !canvas || duration <= 0) return;

    const playheadX = (currentTime / duration) * canvas.getBoundingClientRect().width;
    const viewStart = container.scrollLeft;
    const viewEnd = viewStart + container.clientWidth;
    const margin = Math.min(120, container.clientWidth * 0.25);

    if (playheadX < viewStart + margin || playheadX > viewEnd - margin) {
      container.scrollTo({
        left: Math.max(0, playheadX - container.clientWidth * 0.45),
        behavior: 'smooth',
      });
    }
  }, [currentTime, duration, followPlayhead, zoom]);

  const timeFromPointer = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (!headCanvasRef.current || duration === 0) return;
      const rect = headCanvasRef.current.getBoundingClientRect();
      const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      return ratio * duration;
    },
    [duration],
  );

  const selectWordsForTimeRange = useCallback(
    (startTime: number, endTime: number) => {
      if (words.length === 0) return;
      const start = Math.min(startTime, endTime);
      const end = Math.max(startTime, endTime);
      const indices = [];
      for (let index = 0; index < words.length; index++) {
        const word = words[index];
        if (word.end >= start && word.start <= end) indices.push(index);
      }
      setSelectedWordIndices(indices);
    },
    [setSelectedWordIndices, words],
  );

  const handleMouseDown = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const rawTime = timeFromPointer(e);
      if (rawTime === undefined) return;
      dragStartTimeRef.current = rawTime;
      dragMovedRef.current = false;
      manualScrollPauseUntilRef.current = Date.now() + 1200;
    },
    [timeFromPointer],
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (dragStartTimeRef.current === null) return;
      const rawTime = timeFromPointer(e);
      if (rawTime === undefined) return;
      if (Math.abs(rawTime - dragStartTimeRef.current) < 0.05) return;
      dragMovedRef.current = true;
      selectWordsForTimeRange(dragStartTimeRef.current, rawTime);
    },
    [selectWordsForTimeRange, timeFromPointer],
  );

  const handleMouseUp = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const rawTime = timeFromPointer(e);
      const startTime = dragStartTimeRef.current;
      dragStartTimeRef.current = null;
      if (rawTime === undefined || startTime === null) return;

      if (dragMovedRef.current) {
        selectWordsForTimeRange(startTime, rawTime);
        const direction = rawTime < currentTime ? 'backward' : 'forward';
        const nextTime = getPlayableSeekTime(Math.min(startTime, rawTime), deletedRanges, previewCuts, direction);
        requestSeek(nextTime, direction, false);
        dragMovedRef.current = false;
        return;
      }

      const direction = rawTime < currentTime ? 'backward' : 'forward';
      const nextTime = getPlayableSeekTime(rawTime, deletedRanges, previewCuts, direction);
      requestSeek(nextTime, direction, false);
    },
    [currentTime, deletedRanges, previewCuts, requestSeek, selectWordsForTimeRange, timeFromPointer],
  );

  if (!videoPath) {
    return (
      <div className="w-full h-full flex items-center justify-center text-editor-text-muted text-xs">
        Откройте видео, чтобы увидеть форму волны
      </div>
    );
  }

  return (
    <div ref={containerRef} className="w-full h-full flex flex-col">
      <div className="flex items-center justify-between px-3 py-1 shrink-0">
        <span className="text-[10px] text-editor-text-muted font-medium">
          Звук · монтаж · цензура
        </span>
        <div className="flex items-center gap-1">
          <span className="mr-1 hidden font-mono text-[10px] text-editor-text-muted sm:inline">
            {formatTimelineTime(playbackState.previewTime)} / {formatTimelineTime(playbackState.previewDuration)}
          </span>
          <button
            onClick={() => setFollowPlayhead((current) => !current)}
            className={`p-0.5 ${followPlayhead ? 'text-editor-accent' : 'text-editor-text-muted'} hover:text-editor-text`}
            title={followPlayhead ? 'Следуем за курсором' : 'Следовать за курсором'}
          >
            <LocateFixed className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setZoom((current) => Math.max(1, current - 0.5))}
            disabled={zoom <= 1}
            className="p-0.5 text-editor-text-muted hover:text-editor-text"
            title="Уменьшить масштаб"
          >
            <ZoomOut className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setZoom((current) => Math.min(8, current + 0.5))}
            className="p-0.5 text-editor-text-muted hover:text-editor-text"
            title="Увеличить масштаб"
          >
            <ZoomIn className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
      <div
        className="flex-1 relative overflow-x-auto"
        data-timeline-scroll="true"
        onScroll={() => {
          manualScrollPauseUntilRef.current = Date.now() + 900;
        }}
      >
        <div className="relative h-full min-w-full" style={{ width: `${zoom * 100}%` }}>
          <canvas ref={waveCanvasRef} className="absolute inset-0 h-full w-full" />
          <canvas
            ref={headCanvasRef}
            className="absolute inset-0 h-full w-full cursor-crosshair"
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={() => {
              dragStartTimeRef.current = null;
              dragMovedRef.current = false;
            }}
          />
        </div>
        {audioError && (
          <div className="pointer-events-none absolute inset-x-3 top-2 flex items-center gap-1.5 rounded bg-editor-bg/80 px-2 py-1 text-[10px] text-editor-text-muted">
            <AlertTriangle className="w-3.5 h-3.5 text-yellow-500" />
            <span>{audioError}</span>
          </div>
        )}
        {waveformLoading && !audioError && (
          <div className="pointer-events-none absolute inset-x-3 top-2 rounded bg-editor-bg/80 px-2 py-1 text-[10px] text-editor-text-muted">
            Строим безопасную форму волны…
          </div>
        )}
      </div>
    </div>
  );
}

function formatTimelineTime(seconds: number) {
  const safeSeconds = Math.max(0, Number.isFinite(seconds) ? seconds : 0);
  const minutes = Math.floor(safeSeconds / 60);
  const remaining = Math.floor(safeSeconds % 60);
  return `${minutes}:${remaining.toString().padStart(2, '0')}`;
}

function getSelectedTimeRanges(words: Array<{ start: number; end: number }>, selectedWordIndices: number[]) {
  const sorted = [...new Set(selectedWordIndices)]
    .filter((index) => index >= 0 && index < words.length)
    .sort((a, b) => a - b);
  if (sorted.length === 0) return [];

  const ranges: Array<{ start: number; end: number }> = [];
  let start = sorted[0];
  let previous = sorted[0];

  const flush = () => {
    ranges.push({ start: words[start].start, end: words[previous].end });
  };

  for (let i = 1; i < sorted.length; i++) {
    if (sorted[i] === previous + 1) {
      previous = sorted[i];
      continue;
    }
    flush();
    start = sorted[i];
    previous = sorted[i];
  }
  flush();
  return ranges;
}
