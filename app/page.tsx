'use client';

import {
  ChangeEvent,
  FormEvent,
  ReactNode,
  RefObject,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import { apiBase, studioApi } from './lib/api';
import PracticeGuide from './practice-guide';
import Image from 'next/image';
import type { AmbiguityReason, Capabilities, Cue, DiffPart, Project, Recording, WorkflowView } from './lib/types';

const reasonLabels: Record<AmbiguityReason, string> = {
  word_disagreement: 'Word disagreement',
  low_confidence: 'Low recognition score',
  speaker_mismatch: 'Speaker mismatch',
  timing_drift: 'Timing drift',
  missing_version: 'Missing version',
  missing_source: 'Missing from source',
};

const languageOptions = [
  ['auto', 'Detect automatically'],
  ['en', 'English'],
  ['zh', 'Chinese'],
  ['es', 'Spanish'],
  ['fr', 'French'],
] as const;

function formatTime(milliseconds: number, includeMillis = true) {
  const safe = Math.max(0, milliseconds);
  const hours = Math.floor(safe / 3_600_000);
  const minutes = Math.floor((safe % 3_600_000) / 60_000);
  const seconds = Math.floor((safe % 60_000) / 1000);
  const millis = Math.floor(safe % 1000);
  const prefix = hours ? `${String(hours).padStart(2, '0')}:` : '';
  return `${prefix}${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}${includeMillis ? `.${String(millis).padStart(3, '0')}` : ''}`;
}

function durationLabel(milliseconds: number) {
  if (!milliseconds) return '—';
  const minutes = Math.floor(milliseconds / 60_000);
  const seconds = Math.floor((milliseconds % 60_000) / 1000);
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}

type IconName = 'plus' | 'folder' | 'play' | 'pause' | 'warning' | 'check' | 'film' | 'wave' | 'download' | 'chevron';

function Icon({ name }: { name: IconName }) {
  const paths: Record<IconName, ReactNode> = {
    plus: <path d="M12 5v14M5 12h14" />,
    folder: <path d="M3.5 7.5h6l2-2h3l2 2h4v11h-17z" />,
    play: <path d="m9 7 8 5-8 5z" />,
    pause: <><path d="M9 7v10" /><path d="M15 7v10" /></>,
    warning: <><path d="M12 4 3.5 19h17z" /><path d="M12 9v4" /><path d="M12 16h.01" /></>,
    check: <path d="m5.5 12.5 4 4 9-9" />,
    film: <><rect x="4" y="5" width="16" height="14" rx="2" /><path d="M8 5v14M16 5v14M4 9h4M16 9h4M4 15h4M16 15h4" /></>,
    wave: <path d="M3 12h2l2-6 3 12 3-10 3 8 2-4h3" />,
    download: <><path d="M12 4v11" /><path d="m8 11 4 4 4-4" /><path d="M5 19h14" /></>,
    chevron: <path d="m9 6 6 6-6 6" />,
  };
  return <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

function DiffText({ parts, fallback }: { parts?: DiffPart[]; fallback: string }) {
  if (!parts?.length) return <>{fallback || <span className="empty-version">No text in this version</span>}</>;
  return <>{parts.map((part, index) => <span key={`${part.kind}-${index}`} className={`diff-${part.kind}`}>{part.text}{index < parts.length - 1 ? ' ' : ''}</span>)}</>;
}

function Workflow({ view, setView, recordingCount, segmentCount, remaining, unfinished }: { view: WorkflowView; setView: (view: WorkflowView) => void; recordingCount: number; segmentCount: number; remaining: number; unfinished: number }) {
  const items: { id: WorkflowView; number: number; title: string; detail: string }[] = [
    { id: 'import', number: 1, title: 'Import & process', detail: `${recordingCount} recording${recordingCount === 1 ? '' : 's'}` },
    { id: 'review', number: 2, title: 'Human verification', detail: !recordingCount ? 'Import a recording first' : !segmentCount ? 'Waiting for transcript' : remaining ? `${remaining} need attention` : unfinished ? 'Processing incomplete' : 'Review complete' },
    { id: 'export', number: 3, title: 'Resolve & export', detail: !segmentCount ? 'Nothing to export' : remaining || unfinished ? 'Draft outputs available' : 'Verified outputs' },
  ];
  const activeNumber = items.find(entry => entry.id === view)?.number || 1;
  return <nav className="workflow" aria-label="Project workflow">
    {items.map(item => <button key={item.id} type="button" className={`workflow-step ${view === item.id ? 'is-current' : ''} ${item.number < activeNumber ? 'is-complete' : ''}`} onClick={() => setView(item.id)} aria-current={view === item.id ? 'step' : undefined}>
      <span>{item.number}</span><span><strong>{item.title}</strong><small>{item.detail}</small></span>
    </button>)}
  </nav>;
}

function ProjectBar({ projects, project, onSelect, onCreate, onUpdate, onReviewerDraft }: { projects: Project[]; project: Project | null; onSelect: (id: string) => void; onCreate: (name: string) => Promise<boolean>; onUpdate: (projectId: string, changes: { reviewer?: string }) => Promise<void>; onReviewerDraft: (projectId: string, value: string) => void }) {
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState('');
  const [reviewer, setReviewer] = useState(project?.reviewer || '');
  const [reviewerStatus, setReviewerStatus] = useState('');

  async function saveReviewer() {
    if (!project || reviewer.trim() === (project.reviewer || '')) return;
    setReviewerStatus('Saving…');
    try {
      await onUpdate(project.id, { reviewer: reviewer.trim() });
      setReviewerStatus('Saved');
    } catch (caught) {
      setReviewerStatus(caught instanceof Error ? caught.message : 'Could not save reviewer');
    }
  }

  return <div className="project-bar">
    <label><span className="sr-only">Current project</span><select value={project?.id || ''} onChange={event => onSelect(event.target.value)} disabled={!projects.length}>
      {!projects.length && <option value="">No projects yet</option>}
      {projects.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
    </select></label>
    {creating ? <form className="quick-create" onSubmit={async event => { event.preventDefault(); if (!name.trim()) return; try { if (await onCreate(name.trim())) { setName(''); setCreating(false); } } catch (caught) { setReviewerStatus(caught instanceof Error ? caught.message : 'Could not create project'); } }}>
      <input autoFocus aria-label="New project name" value={name} onChange={event => setName(event.target.value)} placeholder="Project name" maxLength={120} />
      <button className="primary-button compact" type="submit">Create</button>
      <button className="plain-button" type="button" onClick={() => setCreating(false)}>Cancel</button>
    </form> : <button className="plain-button" type="button" onClick={() => setCreating(true)}><Icon name="plus" />New project</button>}
    <label className="reviewer-field"><span>Reviewer</span><input value={reviewer} disabled={!project} maxLength={120} placeholder="Name or initials" aria-label="Reviewer name or initials" onChange={event => { setReviewer(event.target.value); setReviewerStatus('Unsaved'); if (project) onReviewerDraft(project.id, event.target.value); }} onBlur={() => void saveReviewer()} onKeyDown={event => { if (event.key === 'Enter') event.currentTarget.blur(); }} /></label>
    <span className="reviewer-status" role="status" aria-live="polite">{reviewerStatus}</span>
  </div>;
}

function ImportView({ project, capabilities, onImported, onCreateProject }: { project: Project | null; capabilities: Capabilities | null; onImported: (recording: Recording) => Promise<void>; onCreateProject: (name: string) => Promise<boolean> }) {
  const [media, setMedia] = useState<File | null>(null);
  const [source, setSource] = useState<File | null>(null);
  const [tracks, setTracks] = useState<{ file: File; speaker: string }[]>([]);
  const [recordingName, setRecordingName] = useState('');
  const [language, setLanguage] = useState('auto');
  const [dualPass, setDualPass] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [newProjectName, setNewProjectName] = useState('Research Interviews');

  function chooseMedia(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] || null;
    setMedia(selected);
    if (selected && !recordingName) setRecordingName(selected.name.replace(/\.[^.]+$/, ''));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!project || !media || busy) return;
    setBusy(true);
    setError('');
    try {
      const form = new FormData();
      form.append('media', media);
      form.append('recording_name', recordingName.trim() || media.name.replace(/\.[^.]+$/, ''));
      if (source) form.append('source_vtt', source);
      tracks.forEach(track => {
        form.append('speaker_tracks', track.file);
        form.append('speaker_names', track.speaker.trim() || track.file.name.replace(/\.[^.]+$/, ''));
      });
      const imported = await studioApi.importRecording(project.id, form);
      try {
        await studioApi.processRecording(imported.id, {
          model: capabilities?.stt.default_model || 'mlx-community/whisper-large-v3-turbo',
          language,
          dual_pass: dualPass,
        });
      } catch {
        // The import already exists. Open its retryable state rather than inviting a duplicate upload.
      }
      await onImported(imported);
      setMedia(null); setSource(null); setTracks([]); setRecordingName('');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Import failed.');
    } finally {
      setBusy(false);
    }
  }

  if (!project) return <section className="welcome-card">
    <div className="welcome-symbol"><Icon name="wave" /></div>
    <span className="eyebrow">Private by design</span>
    <h1>Create your first local research project</h1>
    <p>Videos, audio, transcripts, model outputs, and edits stay on this computer. A project keeps every recording and its audit history together.</p>
    <form onSubmit={async event => { event.preventDefault(); if (!newProjectName.trim()) return; setError(''); try { await onCreateProject(newProjectName.trim()); } catch (caught) { setError(caught instanceof Error ? caught.message : 'Could not create project.'); } }} className="welcome-form">
      <input value={newProjectName} onChange={event => setNewProjectName(event.target.value)} aria-label="Project name" />
      <button className="primary-button" type="submit">Create project</button>
    </form>
    {error && <p className="error-message" role="alert">{error}</p>}
  </section>;

  return <div className="import-layout">
    <section className="import-card">
      <div className="section-heading"><div><span className="eyebrow">New recording</span><h1>Bring in the original media</h1></div><span className="privacy-pill">Never uploaded</span></div>
      <form onSubmit={submit}>
        <label className={`drop-field ${media ? 'has-file' : ''}`}>
          <input type="file" accept="video/*,audio/*,.m4a,.wav,.mp3,.mp4,.mov,.mkv,.webm" onChange={chooseMedia} />
          <span className="drop-icon"><Icon name={media?.type.startsWith('video/') ? 'film' : 'wave'} /></span>
          <span><strong>{media ? media.name : 'Choose a video or audio file'}</strong><small>{media ? `${(media.size / 1_048_576).toFixed(1)} MB · A preview will be available during review` : 'MP4, MOV, M4A, WAV, MP3, MKV, or WebM'}</small></span>
          <span className="choose-button">Choose…</span>
        </label>

        <div className="form-grid">
          <label className="field"><span>Recording name</span><input value={recordingName} maxLength={160} onChange={event => setRecordingName(event.target.value)} placeholder="Participant or session name" /></label>
          <label className="field"><span>Source transcript <em>optional</em></span><input className="file-input" type="file" accept=".vtt,text/vtt" onChange={event => setSource(event.target.files?.[0] || null)} /></label>
        </div>

        <div className="tracks-section">
          <div className="subheading"><div><strong>Named speaker tracks</strong><small>Optional, but most reliable when each participant has an isolated audio track.</small></div><label className="add-track"><input type="file" multiple accept="audio/*,video/*" onChange={event => {
            const files = Array.from(event.target.files || []);
            setTracks(current => [...current, ...files.map(file => ({ file, speaker: file.name.replace(/\.[^.]+$/, '').replace(/[-_]/g, ' ') }))]);
            event.target.value = '';
          }} /><Icon name="plus" />Add tracks</label></div>
          {tracks.length ? <div className="track-list">{tracks.map((track, index) => <div className="track-row" key={`${track.file.name}-${index}`}>
            <Icon name="wave" /><span title={track.file.name}>{track.file.name}</span><input aria-label={`Speaker for ${track.file.name}`} value={track.speaker} onChange={event => setTracks(current => current.map((item, itemIndex) => itemIndex === index ? { ...item, speaker: event.target.value } : item))} />
            <button className="plain-button danger" type="button" onClick={() => setTracks(current => current.filter((_, itemIndex) => itemIndex !== index))}>Remove</button>
          </div>)}</div> : <p className="empty-note">No separate speaker tracks selected. You can still assign speakers manually during review.</p>}
        </div>

        <div className="processing-options">
          <label className="field"><span>Spoken language</span><select value={language} onChange={event => setLanguage(event.target.value)}>{languageOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label className="toggle-row"><span><strong>Alternate-context second pass</strong><small>Same model, different decoding context. Agreement is not proof of accuracy.</small></span><input type="checkbox" checked={dualPass} onChange={event => setDualPass(event.target.checked)} /><i /></label>
        </div>
        {error && <p className="error-message" role="alert">{error}</p>}
        <div className="submit-row"><span>{capabilities?.stt.active ? `Local engine: ${capabilities.stt.active.replace('_', ' ')}` : 'No compatible local STT engine detected'}</span><button className="primary-button large" type="submit" disabled={!media || busy || !capabilities?.stt.active || !capabilities.ffmpeg || !capabilities.ffprobe}>{busy ? 'Importing safely…' : 'Import & process locally'}</button></div>
      </form>
    </section>

    <aside className="capability-card">
      <span className="eyebrow">This computer</span><h2>Local processing readiness</h2>
      <Capability label="Media tools" ready={Boolean(capabilities?.ffmpeg && capabilities?.ffprobe)} detail="Video preview, extraction, and timing" />
      <Capability label="Speech recognition" ready={Boolean(capabilities?.stt.active)} detail={capabilities?.stt.active ? capabilities.stt.default_model.split('/').pop() || '' : 'Install a supported local engine'} />
      <Capability label="Named speaker tracks" ready={Boolean(capabilities?.speaker_assignment.named_tracks)} detail="Deterministic speaker assignment" />
      <Capability label="Automatic diarization" ready={false} optional detail="Not implemented · use named tracks or manual labels" />
      <div className="local-note"><strong>Where projects live</strong><code>{capabilities?.data_directory || 'Checking local service…'}</code></div>
    </aside>
  </div>;
}

function Capability({ label, ready, detail, optional = false }: { label: string; ready: boolean; detail: string; optional?: boolean }) {
  return <div className="capability-row"><span className={`capability-icon ${ready ? 'ready' : optional ? 'optional' : 'missing'}`}><Icon name={ready ? 'check' : 'warning'} /></span><span><strong>{label}</strong><small>{detail}</small></span></div>;
}

function RecordingSidebar({ recordings, selectedId, onSelect, onImport }: { recordings: Recording[]; selectedId: string | null; onSelect: (id: string) => void; onImport: () => void }) {
  return <aside className="recording-sidebar" aria-label="Recordings">
    <div className="sidebar-heading"><span>Recordings</span><button type="button" className="icon-button" onClick={onImport} aria-label="Import recording"><Icon name="plus" /></button></div>
    <div className="recording-list">{recordings.length ? recordings.map(recording => {
      const total = recording.cue_count || recording.counts?.total || 0;
      const verified = recording.verified_count || recording.counts?.verified || 0;
      return <button type="button" key={recording.id} className={`recording-item ${selectedId === recording.id ? 'is-selected' : ''}`} onClick={() => onSelect(recording.id)} aria-label={`${recording.name}, ${verified} of ${total || 'unprocessed'} verified`}>
        <span className={`recording-state ${recording.status}`} aria-hidden="true" />
        <span className="recording-copy"><strong title={recording.name}>{recording.name}</strong><small>{recording.status === 'processing' ? `${recording.processed_percent}%` : total ? `${verified}/${total}` : durationLabel(recording.duration_ms)}</small></span>
      </button>;
    }) : <div className="sidebar-empty">No recordings yet.</div>}</div>
  </aside>;
}

function ProcessingView({ recording }: { recording: Recording }) {
  return <section className="processing-view"><div className="processing-orb"><span /></div><span className="eyebrow">Local processing</span><h1>{recording.name}</h1><p>{recording.processing_stage}</p><div className="large-progress"><span style={{ width: `${recording.processed_percent}%` }} /></div><strong>{recording.processed_percent}%</strong><small>The media stays on this computer. Long recordings and the alternate-context second pass can take time.</small></section>;
}

function ErrorView({ recording, retry }: { recording: Recording; retry: () => void }) {
  return <section className="processing-view error-view"><div className="error-symbol"><Icon name="warning" /></div><span className="eyebrow">Processing stopped</span><h1>{recording.name}</h1><p>{recording.error || 'The local processing engine reported an error.'}</p><button className="primary-button" onClick={retry}>Try again</button></section>;
}

function ReviewView({ recordings, selectedId, setSelectedId, onImport, refreshProject, reviewer, onDirtyChange }: { recordings: Recording[]; selectedId: string | null; setSelectedId: (id: string) => void; onImport: () => void; refreshProject: () => Promise<void>; reviewer: string; onDirtyChange: (dirty: boolean) => void }) {
  const [recording, setRecording] = useState<Recording | null>(null);
  const [cues, setCues] = useState<Cue[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [filter, setFilter] = useState<'all' | 'everything' | 'verified' | AmbiguityReason>('all');
  const [finalText, setFinalText] = useState('');
  const [speaker, setSpeaker] = useState('Unknown speaker');
  const [startMs, setStartMs] = useState(0);
  const [endMs, setEndMs] = useState(0);
  const [speed, setSpeed] = useState(1);
  const [looping, setLooping] = useState(true);
  const [playing, setPlaying] = useState(false);
  const [notice, setNotice] = useState('');
  const [loadError, setLoadError] = useState('');
  const [saving, setSaving] = useState(false);
  const operationRef = useRef(false);
  const [history, setHistory] = useState<string>('');
  const mediaRef = useRef<HTMLMediaElement>(null);

  const openCue = useCallback((cue: Cue, index: number) => {
    setActiveIndex(index);
    setFinalText(cue.final_text);
    setSpeaker(cue.speaker);
    setStartMs(cue.start_ms);
    setEndMs(cue.end_ms);
    setNotice('');
    setHistory('');
    mediaRef.current?.pause();
    if (mediaRef.current) mediaRef.current.currentTime = Math.max(0, cue.start_ms / 1000 - 1.5);
  }, []);

  const loadRecording = useCallback(async (id: string) => {
    const [nextRecording, nextCues] = await Promise.all([studioApi.recording(id), studioApi.cues(id)]);
    setLoadError('');
    setRecording(nextRecording);
    setCues(nextCues);
    const first = nextCues.find(cue => cue.status !== 'verified') || nextCues[0];
    if (first) openCue(first, nextCues.indexOf(first));
  }, [openCue]);

  useEffect(() => {
    if (!selectedId) return;
    const timer = window.setTimeout(() => void loadRecording(selectedId).catch(caught => {
      setLoadError(caught instanceof Error ? caught.message : 'Could not load this recording.');
    }), 0);
    return () => window.clearTimeout(timer);
  }, [selectedId, loadRecording]);

  useEffect(() => {
    if (recording?.status !== 'processing') return;
    const timer = window.setInterval(async () => {
      try {
        const next = await studioApi.recording(recording.id);
        setLoadError('');
        setRecording(next);
        await refreshProject();
        if (next.status === 'ready' || next.status === 'error') await loadRecording(next.id);
      } catch (caught) {
        setLoadError(caught instanceof Error ? caught.message : 'Lost connection to the local service.');
      }
    }, 1800);
    return () => window.clearInterval(timer);
  }, [recording?.id, recording?.status, loadRecording, refreshProject]);

  const filteredCues = useMemo(() => cues.filter(cue => filter === 'everything' || (filter === 'verified' ? cue.status === 'verified' : cue.status !== 'verified' && (filter === 'all' || cue.ambiguity_reasons.includes(filter)))), [cues, filter]);
  const activeCue = cues[activeIndex] || null;
  const activeFilteredIndex = activeCue ? filteredCues.findIndex(cue => cue.id === activeCue.id) : -1;
  const hasUnsavedChanges = Boolean(activeCue && (
    finalText !== activeCue.final_text || speaker !== activeCue.speaker || startMs !== activeCue.start_ms || endMs !== activeCue.end_ms
  ));

  useEffect(() => onDirtyChange(hasUnsavedChanges), [hasUnsavedChanges, onDirtyChange]);
  useEffect(() => () => onDirtyChange(false), [onDirtyChange]);
  useEffect(() => {
    function warnBeforeUnload(event: BeforeUnloadEvent) {
      if (!hasUnsavedChanges) return;
      event.preventDefault();
      event.returnValue = '';
    }
    window.addEventListener('beforeunload', warnBeforeUnload);
    return () => window.removeEventListener('beforeunload', warnBeforeUnload);
  }, [hasUnsavedChanges]);

  const confirmDiscard = useCallback(() => !hasUnsavedChanges || window.confirm('Discard the unsaved changes to this cue?'), [hasUnsavedChanges]);

  useEffect(() => { if (mediaRef.current) mediaRef.current.playbackRate = speed; }, [speed]);

  const chooseCue = useCallback((cue: Cue) => {
    if (operationRef.current) return;
    if (cue.id !== activeCue?.id && !confirmDiscard()) return;
    const index = cues.findIndex(item => item.id === cue.id);
    if (index >= 0) openCue(cue, index);
  }, [activeCue?.id, confirmDiscard, cues, openCue]);

  const selectRecording = useCallback((id: string) => {
    if (id !== selectedId && !confirmDiscard()) return;
    setSelectedId(id);
  }, [confirmDiscard, selectedId, setSelectedId]);
  const startImport = useCallback(() => {
    if (confirmDiscard()) onImport();
  }, [confirmDiscard, onImport]);

  const playCue = useCallback(async () => {
    if (!mediaRef.current || !activeCue) return;
    if (!mediaRef.current.paused) { mediaRef.current.pause(); return; }
    if (mediaRef.current.currentTime * 1000 < activeCue.start_ms - 2000 || mediaRef.current.currentTime * 1000 > activeCue.end_ms + 500) mediaRef.current.currentTime = Math.max(0, activeCue.start_ms / 1000 - 1.5);
    try { await mediaRef.current.play(); }
    catch { setNotice('Playback could not start. Try the video controls, or convert this file to MP4 (H.264/AAC) and import it again.'); }
  }, [activeCue]);

  const moveRelative = useCallback((seconds: number) => {
    if (!mediaRef.current) return;
    mediaRef.current.currentTime = Math.max(0, mediaRef.current.currentTime + seconds);
  }, []);

  const nextAttention = useCallback(() => {
    if (!filteredCues.length) return;
    const next = filteredCues[(Math.max(activeFilteredIndex, -1) + 1) % filteredCues.length];
    chooseCue(next);
  }, [activeFilteredIndex, chooseCue, filteredCues]);

  const previousAttention = useCallback(() => {
    if (!filteredCues.length) return;
    const previous = filteredCues[(Math.max(activeFilteredIndex, 0) - 1 + filteredCues.length) % filteredCues.length];
    chooseCue(previous);
  }, [activeFilteredIndex, chooseCue, filteredCues]);

  const save = useCallback(async (status: Cue['status'] = 'verified', advance = true) => {
    if (!activeCue || operationRef.current) return;
    operationRef.current = true;
    setSaving(true);
    try {
      const updated = await studioApi.updateCue(activeCue.id, { final_text: finalText.trim(), speaker, start_ms: startMs, end_ms: endMs, status, reviewer, expected_revision: activeCue.revision });
      const updatedCues = cues.map(cue => cue.id === updated.id ? updated : cue);
      setCues(updatedCues);
      let totalsWarning = '';
      try { await refreshProject(); } catch { totalsWarning = ' Project totals will refresh after reconnection.'; }
      const savedNotice = reviewer
        ? `Saved as ${status} with an attributable audit entry.`
        : `Saved as ${status}. Reviewer was not recorded for this action.`;
      if (advance) {
        const remaining = updatedCues.filter(cue => cue.status !== 'verified' && (filter === 'all' || filter === 'everything' || filter === 'verified' || cue.ambiguity_reasons.includes(filter)));
        const next = remaining.find(cue => cue.cue_index > updated.cue_index) || remaining[0];
        if (next) openCue(next, updatedCues.findIndex(cue => cue.id === next.id));
        else openCue(updated, updatedCues.findIndex(cue => cue.id === updated.id));
        setNotice(next ? `${savedNotice}${totalsWarning}` : `${savedNotice} No cues remain in this queue.${totalsWarning}`);
      } else {
        openCue(updated, updatedCues.findIndex(cue => cue.id === updated.id));
        setNotice(`${savedNotice}${totalsWarning}`);
      }
    } catch (caught) { setNotice(caught instanceof Error ? caught.message : 'Could not save this cue.'); }
    finally { operationRef.current = false; setSaving(false); }
  }, [activeCue, cues, endMs, filter, finalText, openCue, refreshProject, reviewer, speaker, startMs]);

  async function splitAtPlayhead() {
    if (!activeCue || !mediaRef.current || operationRef.current) return;
    operationRef.current = true;
    setSaving(true);
    const splitMs = Math.round(mediaRef.current.currentTime * 1000);
    try {
      const next = await studioApi.splitCue(activeCue.id, {
        split_ms: splitMs,
        final_text: finalText.trim(),
        speaker,
        start_ms: startMs,
        end_ms: endMs,
        reviewer,
        expected_revision: activeCue.revision,
      });
      setCues(next);
      try { await refreshProject(); } catch { /* The split is already committed; totals refresh on the next request. */ }
      const updatedLeft = next.find(cue => cue.id === activeCue.id);
      if (updatedLeft) openCue(updatedLeft, next.findIndex(cue => cue.id === updatedLeft.id));
      setNotice(`Split at ${formatTime(splitMs)}. Text was divided approximately; listen and adjust both cues. Original evidence remains in the audit history.`);
    } catch (caught) { setNotice(caught instanceof Error ? caught.message : 'Could not split this cue.'); }
    finally { operationRef.current = false; setSaving(false); }
  }

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const editing = target?.matches('textarea,input,select,[contenteditable="true"]');
      if (operationRef.current) return;
      if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') { event.preventDefault(); void save('verified', true); return; }
      if (editing || event.metaKey || event.ctrlKey || event.altKey || target?.closest('button,a,summary,video')) return;
      if (event.code === 'Space') { event.preventDefault(); void playCue(); }
      if (event.key === '1' && activeCue) setFinalText(activeCue.source_text);
      if (event.key === '2' && activeCue) setFinalText(activeCue.stt_a_text);
      if (event.key === '3' && activeCue) setFinalText(activeCue.stt_b_text);
      if (event.key.toLowerCase() === 'u') void save('unclear', true);
      if (event.key === 'ArrowDown') { event.preventDefault(); nextAttention(); }
      if (event.key === 'ArrowUp') { event.preventDefault(); previousAttention(); }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [activeCue, nextAttention, playCue, previousAttention, save]);

  if (loadError) return <div className="review-workspace"><RecordingSidebar recordings={recordings} selectedId={selectedId} onSelect={selectRecording} onImport={startImport} /><section className="empty-review"><Icon name="warning" /><h1>Could not load this recording</h1><p>{loadError}</p>{selectedId && <button className="primary-button" onClick={() => void loadRecording(selectedId).catch(caught => setLoadError(caught instanceof Error ? caught.message : 'Could not load this recording.'))}>Try again</button>}</section></div>;
  if (!recording) return <div className="review-workspace"><RecordingSidebar recordings={recordings} selectedId={selectedId} onSelect={selectRecording} onImport={startImport} /><section className="empty-review"><Icon name="film" /><h1>Select a recording</h1><p>Import a video or audio file, then choose it here for human verification.</p><button className="primary-button" onClick={startImport}>Import recording</button></section></div>;
  if (recording.status === 'processing') return <div className="review-workspace"><RecordingSidebar recordings={recordings} selectedId={selectedId} onSelect={selectRecording} onImport={startImport} /><ProcessingView recording={recording} /></div>;
  if (recording.status === 'error' || recording.status === 'imported') return <div className="review-workspace"><RecordingSidebar recordings={recordings} selectedId={selectedId} onSelect={selectRecording} onImport={startImport} /><ErrorView recording={recording.status === 'imported' ? { ...recording, error: 'Your recording is imported safely. Processing has not started; choose Try again to start the local model.' } : recording} retry={async () => {
    try {
      setLoadError('');
      await studioApi.processRecording(recording.id, { model: recording.metadata.model || 'mlx-community/whisper-large-v3-turbo', language: recording.metadata.language || 'auto', dual_pass: recording.metadata.dual_pass ?? true });
      await loadRecording(recording.id);
    } catch (caught) {
      setLoadError(caught instanceof Error ? caught.message : 'Could not restart local processing.');
    }
  }} /></div>;
  if (!activeCue) return <div className="review-workspace"><RecordingSidebar recordings={recordings} selectedId={selectedId} onSelect={selectRecording} onImport={startImport} /><section className="empty-review"><Icon name="warning" /><h1>No transcript cues were created</h1><p>Check that the media contains audible speech or import a source VTT.</p></section></div>;

  const reasonCounts = Object.keys(reasonLabels).reduce((result, reason) => ({ ...result, [reason]: cues.filter(cue => cue.ambiguity_reasons.includes(reason as AmbiguityReason) && cue.status !== 'verified').length }), {} as Record<AmbiguityReason, number>);
  const speakerOptions = Array.from(new Set([...(recording.speakers || []), ...cues.map(cue => cue.speaker), 'Unknown speaker']));

  return <div className="review-workspace">
    <RecordingSidebar recordings={recordings} selectedId={selectedId} onSelect={selectRecording} onImport={startImport} />
    <section className="review-surface" aria-label="Transcript verification">
      <div className="segment-browser">
        <label>Browse <select aria-label="Review queue" value={filter} disabled={saving} onChange={event => setFilter(event.target.value as typeof filter)}>
          <option value="all">All unresolved</option><option value="everything">All segments</option><option value="verified">Verified segments</option>
          {(Object.keys(reasonLabels) as AmbiguityReason[]).map(reason => <option key={reason} value={reason}>{reasonLabels[reason]}</option>)}
        </select></label>
        <label>Go to <select aria-label="Go to segment" value={activeCue.id} disabled={saving} onChange={event => { const cue = cues.find(item => item.id === Number(event.target.value)); if (cue) chooseCue(cue); }}>
          {!filteredCues.some(cue => cue.id === activeCue.id) && <option value={activeCue.id}>Current · {activeCue.cue_index}</option>}
          {filteredCues.map(cue => <option key={cue.id} value={cue.id}>{cue.cue_index} · {formatTime(cue.start_ms, false)} · {cue.status}</option>)}
        </select></label>
        <span>{filteredCues.length} in this queue</span>
      </div>
      <div className="cue-header"><div><span className="eyebrow">Cue {activeCue.cue_index} of {cues.length}</span><h1>Verify this spoken segment</h1></div><div className="cue-header-actions"><div className="cue-meta"><span>{formatTime(activeCue.start_ms)}–{formatTime(activeCue.end_ms)}</span><span className={`ambiguity-badge ${activeCue.status === 'verified' ? 'verified' : ''}`}>{activeCue.status === 'verified' ? 'Verified' : activeCue.status === 'unclear' ? 'Marked unclear' : `${activeCue.ambiguity_score} ambiguity`}</span></div><div className="cue-navigation" aria-label="Cue navigation"><button type="button" className="secondary-button" disabled={!filteredCues.length} onClick={previousAttention}>Previous</button><button type="button" className="secondary-button" disabled={!filteredCues.length} onClick={nextAttention}>Next</button></div></div></div>

      <section className={`media-panel ${recording.metadata.media_type === 'video' ? 'has-video' : ''}`} aria-label="Media preview">
        {recording.metadata.media_type === 'video'
          ? <video ref={mediaRef as RefObject<HTMLVideoElement>} src={studioApi.mediaUrl(recording.id)} preload="metadata" controls playsInline onLoadedMetadata={event => { event.currentTarget.currentTime = Math.max(0, startMs / 1000 - 1.5); }} onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onTimeUpdate={event => {
            const element = event.currentTarget;
            if (looping && !element.paused && element.currentTime * 1000 >= endMs + 850) element.currentTime = Math.max(0, startMs / 1000 - 0.7);
          }} />
          : <div className="audio-visual"><div className="audio-symbol"><Icon name="wave" /></div><div><strong>{recording.name}</strong><small>Audio preview · {durationLabel(recording.duration_ms)}</small></div><audio ref={mediaRef as RefObject<HTMLAudioElement>} src={studioApi.mediaUrl(recording.id)} preload="metadata" onLoadedMetadata={event => { event.currentTarget.currentTime = Math.max(0, startMs / 1000 - 1.5); }} onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onTimeUpdate={event => { const element = event.currentTarget; if (looping && !element.paused && element.currentTime * 1000 >= endMs + 850) element.currentTime = Math.max(0, startMs / 1000 - 0.7); }} /></div>}
        <div className="player-toolbar"><div className="transport-controls"><button type="button" className="secondary-button" onClick={() => moveRelative(-5)}>−5 s</button><button type="button" className="play-button" onClick={() => void playCue()}><Icon name={playing ? 'pause' : 'play'} />{playing ? 'Pause' : 'Play cue'}</button><button type="button" className={`secondary-button ${looping ? 'is-active' : ''}`} aria-pressed={looping} onClick={() => setLooping(value => !value)}>Loop cue</button><button type="button" className="secondary-button" onClick={() => moveRelative(5)}>+5 s</button></div><label className="speed-control"><span>Speed</span><select value={speed} onChange={event => setSpeed(Number(event.target.value))}><option value={0.75}>0.75×</option><option value={1}>1.0×</option><option value={1.25}>1.25×</option><option value={1.5}>1.5×</option><option value={2}>2.0×</option></select></label></div>
      </section>

      <fieldset disabled={saving} className="review-edit-fields">
      <section className="comparison-panel" aria-label="Transcript comparison"><div className="panel-heading"><div><h2>Listen, choose, then refine</h2></div><span className="panel-hint">{activeCue.source_text ? 'Differences against the source are highlighted' : 'No source wording is available for this segment'}</span></div>
        <VersionRow number="1" label="Source VTT" meta={activeCue.source_text ? 'Imported transcript' : 'No source wording at this time'} text={activeCue.source_text} onUse={() => setFinalText(activeCue.source_text)} />
        <VersionRow number="2" label="Local STT A" meta={activeCue.confidence_a ? `${Math.round(activeCue.confidence_a * 100)} recognition score · Context-aware` : 'Context-aware pass'} text={activeCue.stt_a_text} parts={activeCue.diff_source_a} onUse={() => setFinalText(activeCue.stt_a_text)} />
        <VersionRow number="3" label="Local STT B" meta={activeCue.confidence_b ? `${Math.round(activeCue.confidence_b * 100)} recognition score · Alternate context` : 'Alternate-context pass'} text={activeCue.stt_b_text} parts={activeCue.diff_source_b} onUse={() => setFinalText(activeCue.stt_b_text)} />
      </section>

      <section className="editor-panel" aria-label="Transcript editor"><div className="editor-heading"><label htmlFor="verified-text"><strong>Transcript editor</strong><small>Save the cue as verified only after listening and checking this text.</small></label><div className="editor-context"><span className={reviewer ? 'reviewer-present' : 'reviewer-missing'}>{reviewer ? `Reviewer: ${reviewer}` : 'Reviewer not set'}</span><label className="speaker-control"><span className="sr-only">Speaker</span><input aria-label="Speaker" list="speaker-suggestions" value={speaker} maxLength={120} onChange={event => setSpeaker(event.target.value)} /><datalist id="speaker-suggestions">{speakerOptions.map(value => <option key={value} value={value} />)}</datalist></label></div></div>
        <textarea id="verified-text" value={finalText} onChange={event => setFinalText(event.target.value)} spellCheck />
        <div className="timing-editor"><label>Start <input type="number" step="0.001" value={(startMs / 1000).toFixed(3)} onChange={event => setStartMs(Math.round(Number(event.target.value) * 1000))} /><span>s</span></label><label>End <input type="number" step="0.001" value={(endMs / 1000).toFixed(3)} onChange={event => setEndMs(Math.round(Number(event.target.value) * 1000))} /><span>s</span></label><button type="button" className="secondary-button" onClick={splitAtPlayhead}>Split at playhead</button></div>
        <div className="editor-actions"><div className="edit-tools"><button type="button" className="secondary-button" onClick={() => void save('unclear', true)}>Mark unclear</button><button type="button" className="secondary-button" onClick={() => { if (mediaRef.current) { setStartMs(Math.round(mediaRef.current.currentTime * 1000)); setNotice('Start time set to the playhead.'); } }}>Set start</button><button type="button" className="secondary-button" onClick={() => { if (mediaRef.current) { setEndMs(Math.round(mediaRef.current.currentTime * 1000)); setNotice('End time set to the playhead.'); } }}>Set end</button></div><button type="button" className="primary-button" disabled={!finalText.trim() || saving} onClick={() => void save('verified', true)}>{saving ? 'Saving…' : 'Save & next'}</button></div>
        <div className="draft-tools"><button type="button" className="plain-button" onClick={() => void save('pending', false)}>Save draft</button><button type="button" className="plain-button" onClick={async () => {
          try { const entries = await studioApi.history(activeCue.id); setHistory(entries.length ? entries.map(entry => `${entry.action} · ${entry.reviewer} · ${new Date(entry.created_at).toLocaleString()}`).join('\n') : 'No human actions recorded for this segment yet.'); }
          catch (caught) { setHistory(caught instanceof Error ? caught.message : 'History unavailable'); }
        }}>Review history</button><span>{hasUnsavedChanges ? 'Unsaved changes' : 'Saved state'}</span></div>
        <div className="shortcut-row"><span><kbd>Space</kbd> Play</span><span><kbd>1</kbd><kbd>2</kbd><kbd>3</kbd> Use version</span><span><kbd>U</kbd> Unclear</span><span><kbd>↑</kbd><kbd>↓</kbd> Navigate</span><span><kbd>⌘</kbd><kbd>↩</kbd> Save & next</span></div><p className="notice" role="status" aria-live="polite">{notice}</p>
        {history && <pre className="history-summary" aria-label="Review history">{history}</pre>}
      </section>
      </fieldset>
    </section>

    <aside className="queue-sidebar" aria-label="Attention queue"><div className="sidebar-heading"><span>Attention queue</span><strong>{cues.filter(cue => cue.status !== 'verified').length}</strong></div><div className="queue-filters"><button className={filter === 'all' ? 'is-selected' : ''} onClick={() => setFilter('all')}><span>All unresolved</span><strong>{cues.filter(cue => cue.status !== 'verified').length}</strong></button>{(Object.keys(reasonLabels) as AmbiguityReason[]).map(reason => <button key={reason} className={filter === reason ? 'is-selected' : ''} onClick={() => setFilter(reason)}><span>{reasonLabels[reason]}</span><strong>{reasonCounts[reason]}</strong></button>)}</div><div className="cue-queue">{filteredCues.map(cue => <button key={cue.id} className={cue.id === activeCue.id ? 'is-current' : ''} onClick={() => chooseCue(cue)}><span>{cue.cue_index}</span><span><strong>{cue.final_text || cue.stt_a_text || 'No transcript text'}</strong><small>{formatTime(cue.start_ms, false)} · {cue.ambiguity_score} ambiguity</small></span><Icon name="chevron" /></button>)}</div></aside>
  </div>;
}

function VersionRow({ number, label, meta, text, parts, onUse }: { number: string; label: string; meta: string; text: string; parts?: DiffPart[]; onUse: () => void }) {
  return <article className="comparison-row"><div className="version-label"><span className="number-key">{number}</span><span><strong>{label}</strong><small title={meta}>{meta}</small></span></div><p><DiffText parts={parts} fallback={text} /></p><button type="button" className="use-button" aria-label={`Use ${label}`} onClick={onUse} disabled={!text}>Use</button></article>;
}

function ExportView({ project, recordings, setView, onSelect }: { project: Project | null; recordings: Recording[]; setView: (view: WorkflowView) => void; onSelect: (id: string) => void }) {
  if (!project) return <section className="empty-review"><Icon name="download" /><h1>No project to export</h1><p>Create a project and verify at least one recording first.</p><button className="primary-button" onClick={() => setView('import')}>Start a project</button></section>;
  const total = recordings.reduce((sum, item) => sum + (item.cue_count || 0), 0);
  const unresolved = recordings.reduce((sum, item) => sum + Math.max(0, (item.cue_count || 0) - (item.verified_count || 0)), 0);
  const canExport = total > 0;
  const unfinished = recordings.filter(item => item.status !== 'ready' || !item.cue_count).length;
  return <div className="export-layout">
    <section className="export-hero">
      <span className="export-icon"><Icon name="download" /></span>
      <span className="eyebrow">Qualitative analysis package</span>
      <h1>Export analysis-ready research data</h1>
      <p>A documented, traceable package for NVivo, MAXQDA, ATLAS.ti, spreadsheets, and long-term research reuse.</p>
      <div className="export-stats"><span><strong>{recordings.length}</strong> recordings</span><span><strong>{total}</strong> segments</span><span className={unresolved ? 'warn' : 'good'}><strong>{unresolved}</strong> unresolved</span></div>
      <div className="package-includes" aria-label="Package contents">
        <span><Icon name="check" />Analysis DOCX + NVivo DOCX</span>
        <span><Icon name="check" />Structured CSV + XLSX</span>
        <span><Icon name="check" />Synced VTT + SRT</span>
        <span><Icon name="check" />Metadata, audit + checksums</span>
      </div>
      <a aria-disabled={!canExport} className={`primary-button large download-link ${!canExport ? 'disabled' : ''}`} href={canExport ? studioApi.bundleUrl(project.id) : undefined}><Icon name="download" />{unresolved ? 'Download draft analysis package' : 'Download analysis package'}</a>
      <a aria-disabled={!canExport} className={`secondary-button large download-link restricted-download ${!canExport ? 'disabled' : ''}`} href={canExport ? studioApi.bundleUrl(project.id, true) : undefined} onClick={event => { if (!canExport || !window.confirm('This restricted package includes original voice and video. Continue only if the destination is approved for identifiable research data.')) event.preventDefault(); }}><Icon name="film" />Include original media</a>
      <small>Media is excluded by default. Identity risk is not automatically assessed; review the package before sharing.</small>
      {unresolved > 0 && <p className="export-warning"><Icon name="warning" />This is a draft. Keep the package metadata for per-segment status; SRT captions cannot carry review status.</p>}
      {unfinished > 0 && <p className="export-warning">{unfinished} recording(s) still need processing. This project is not complete.</p>}
    </section>
    <section className="export-list">
      <div className="section-heading"><div><span className="eyebrow">Per recording</span><h2>Researcher-ready formats</h2></div></div>
      {recordings.map(recording => {
        const remaining = Math.max(0, (recording.cue_count || 0) - (recording.verified_count || 0));
        const ready = Boolean(recording.cue_count) && recording.status === 'ready';
        return <article className="export-row" key={recording.id}>
          <div className={`export-state ${remaining || !ready ? 'warn' : 'good'}`}><Icon name={remaining || !ready ? 'warning' : 'check'} /></div>
          <div><strong>{recording.name}</strong><small>{recording.cue_count || 0} segments · {!ready ? 'Processing incomplete' : remaining ? `${remaining} still unresolved` : 'Human review complete'}</small></div>
          {ready && <div className="format-links">
            <a className="analysis-link" href={studioApi.exportUrl(recording.id, 'docx')}>DOCX</a>
            <a className="analysis-link" href={studioApi.exportUrl(recording.id, 'nvivo')}>NVivo</a>
            <a className="analysis-link" href={studioApi.exportUrl(recording.id, 'xlsx')}>XLSX</a>
            <a href={studioApi.exportUrl(recording.id, 'vtt')}>VTT</a>
            <a href={studioApi.exportUrl(recording.id, 'srt')}>SRT</a>
            <a href={studioApi.exportUrl(recording.id, 'csv')}>CSV</a>
            <a href={studioApi.exportUrl(recording.id, 'json')}>JSON</a>
            <a href={studioApi.exportUrl(recording.id, 'txt')}>TXT</a>
            <a className="change-link" href={studioApi.exportUrl(recording.id, 'changes')}>Changes</a>
            <a className="change-link" href={studioApi.exportUrl(recording.id, 'report')}>Report</a>
          </div>}
          <button className="plain-button" onClick={() => { onSelect(recording.id); setView('review'); }}>Review</button>
        </article>;
      })}
    </section>
  </div>;
}

export default function Home() {
  const [view, setView] = useState<WorkflowView>('import');
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [selectedRecordingId, setSelectedRecordingId] = useState<string | null>(null);
  const [serviceError, setServiceError] = useState('');
  const [initializing, setInitializing] = useState(true);
  const [reviewDirty, setReviewDirty] = useState(false);
  const [navigationError, setNavigationError] = useState('');
  const [reviewerDraft, setReviewerDraft] = useState<{ projectId: string; value: string } | null>(null);
  const selectionRequest = useRef(0);

  const refreshProject = useCallback(async (id = project?.id) => {
    if (!id) return;
    const next = await studioApi.project(id); setProject(current => current?.id === next.id ? next : current);
    setProjects(current => current.map(item => item.id === next.id ? next : item));
  }, [project?.id]);

  useEffect(() => {
    void (async () => {
      try {
        const nextCapabilities = await studioApi.capabilities();
        const practiceRequested = new URLSearchParams(window.location.search).get('practice') === '1';
        if (practiceRequested !== nextCapabilities.practice_mode) throw new Error('The selected service does not match this workspace. Close it and use the correct launcher.');
        const nextProjects = await studioApi.projects();
        setCapabilities(nextCapabilities); setProjects(nextProjects);
        if (nextProjects[0]) { const full = await studioApi.project(nextProjects[0].id); setProject(full); setSelectedRecordingId(full.recordings?.[0]?.id || null); if (practiceRequested && full.recordings?.length) setView('review'); }
      } catch (caught) {
        setServiceError(caught instanceof Error ? caught.message : `Start the local service at ${apiBase()}, then reload this page.`);
      } finally {
        setInitializing(false);
      }
    })();
  }, []);

  const confirmDiscardReview = useCallback(() => !reviewDirty || window.confirm('Discard the unsaved changes to the current cue?'), [reviewDirty]);

  const changeView = useCallback((nextView: WorkflowView) => {
    if (nextView === view || !confirmDiscardReview()) return;
    setReviewDirty(false);
    setView(nextView);
  }, [confirmDiscardReview, view]);

  const createProject = useCallback(async (name: string) => {
    if (!confirmDiscardReview()) return false;
    const created = await studioApi.createProject(name); setProjects(current => [created, ...current]); setProject(created); setSelectedRecordingId(null); setView('import');
    setReviewDirty(false);
    return true;
  }, [confirmDiscardReview]);

  const updateProject = useCallback(async (projectId: string, changes: { reviewer?: string }) => {
    const updated = await studioApi.updateProject(projectId, changes);
    setProject(current => current?.id === updated.id ? updated : current);
    setProjects(current => current.map(item => item.id === updated.id ? updated : item));
  }, []);

  async function selectProject(id: string) {
    if (!confirmDiscardReview()) return;
    const requestId = ++selectionRequest.current;
    try {
      const next = await studioApi.project(id);
      if (requestId !== selectionRequest.current) return;
      setProject(next); setSelectedRecordingId(next.recordings?.[0]?.id || null);
      setReviewDirty(false); setNavigationError('');
    } catch (caught) { setNavigationError(caught instanceof Error ? caught.message : 'Could not open this project.'); }
  }

  async function imported(recording: Recording) {
    await refreshProject(recording.project_id);
    if (project?.id === recording.project_id) { setSelectedRecordingId(recording.id); setView('review'); }
  }

  const recordings = project?.recordings || [];
  const segmentCount = recordings.reduce((sum, item) => sum + (item.cue_count || 0), 0);
  const remaining = recordings.reduce((sum, item) => sum + Math.max(0, (item.cue_count || 0) - (item.verified_count || 0)), 0);

  if (serviceError) return <main className="service-error"><div className="window-controls" aria-hidden="true"><span className="window-dot close-dot" /><span className="window-dot minimize-dot" /><span className="window-dot zoom-dot" /></div><div className="error-symbol"><Icon name="warning" /></div><h1>Local service unavailable</h1><p>{serviceError}</p><button className="primary-button" onClick={() => window.location.reload()}>Try again</button></main>;

  if (initializing) return <main className="service-error" aria-busy="true"><Image src="/logo.svg" alt="" width={48} height={48} priority /><h1>Opening your local workspace</h1><p role="status">Checking the local service and loading your projects…</p></main>;

  return <main className="app-shell">
    <a className="skip-link" href="#workspace">Skip to workspace</a>
    <header className="titlebar"><Image src="/logo.svg" alt="" width={30} height={30} priority /><div className="product-title"><strong>Transcript Review Studio</strong><span>{project?.name || 'Local research workspace'}</span></div><div className="local-status"><span className="status-dot" aria-hidden="true" />{capabilities?.practice_mode ? 'Practice workspace' : 'Local only'}</div></header>
    <ProjectBar key={project?.id || 'no-project'} projects={projects} project={project} onSelect={selectProject} onCreate={createProject} onUpdate={updateProject} onReviewerDraft={(projectId, value) => setReviewerDraft({ projectId, value })} />
    <Workflow view={view} setView={changeView} recordingCount={recordings.length} segmentCount={segmentCount} remaining={remaining} unfinished={recordings.filter(item => item.status !== 'ready' || !item.cue_count).length} />
    {navigationError && <p className="error-message" role="alert">{navigationError}</p>}
    {capabilities?.practice_mode && <PracticeGuide onNavigate={changeView} />}
    <div className="content-area" id="workspace" tabIndex={-1}>
      {view === 'import' && <ImportView key={project?.id || 'new'} project={project} capabilities={capabilities} onImported={imported} onCreateProject={createProject} />}
      {view === 'review' && <ReviewView key={`${project?.id || 'no-project'}:${selectedRecordingId || 'no-recording'}`} recordings={recordings} selectedId={selectedRecordingId} setSelectedId={setSelectedRecordingId} onImport={() => { setReviewDirty(false); setView('import'); }} refreshProject={refreshProject} reviewer={(reviewerDraft?.projectId === project?.id ? reviewerDraft?.value : project?.reviewer)?.trim() || ''} onDirtyChange={setReviewDirty} />}
      {view === 'export' && <ExportView project={project} recordings={recordings} setView={setView} onSelect={setSelectedRecordingId} />}
    </div>
  </main>;
}
