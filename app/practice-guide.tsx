'use client';

import { useState } from 'react';
import { apiBase } from './lib/api';
import type { WorkflowView } from './lib/types';

const steps = [
  ['Preview the conversation', 'Play the public video. Try 0.75× speed, ±5 seconds, and cue looping. Check that sound and picture stay aligned.'],
  ['Compare and edit', 'Compare Source, STT A, and STT B. The practice baseline contains clearly labelled seeded errors, not a gold-standard transcript. Listen before changing a word.'],
  ['Save without certifying', 'Enter reviewer initials and wait for “Saved”. Change the text, choose Save draft, then reopen the segment. Confirm the edit is retained and still pending.'],
  ['Verify and revisit', 'After listening, choose Save & next. Select Verified segments in Browse, then reopen your segment. Check Review history for your initials.'],
  ['Keep an uncertainty', 'Choose another segment and Mark unclear. It must remain in All unresolved and prevent a fully verified export.'],
  ['Check edit protection', 'Type a temporary edit, then choose another segment. Cancel the discard prompt and confirm the text remains. Restore or save your draft.'],
  ['Adjust timing and split', 'Move the playhead inside a segment and choose Split at playhead. Both pieces must be pending; check their wording and timestamps manually.'],
  ['Export and inspect', 'Open Resolve & export. Download the draft analysis package. Inspect DOCX, XLSX, and the English change log. No original media should be included by default.'],
  ['Try an import yourself', 'Download the public sample below, create a practice project, and import it without a VTT. Wait for both local passes; nothing should be labelled human-verified.'],
  ['Restart and resume', 'Save your work, reload the page or restart the practice launcher, and confirm your edits survive. Do not mark this check until you have done it.'],
] as const;
const KEY = 'trs-practice-checklist-v1.3';

export default function PracticeGuide({ onNavigate }: { onNavigate: (view: WorkflowView) => void }) {
  const [open, setOpen] = useState(true);
  const [section, setSection] = useState<'learn' | 'test'>('learn');
  const [checked, setChecked] = useState<number[]>(() => {
    try { const value: unknown = JSON.parse(localStorage.getItem(KEY) || '[]'); return Array.isArray(value) ? value.filter(item => Number.isInteger(item) && item >= 0 && item < steps.length) : []; }
    catch { return []; }
  });
  const [notes, setNotes] = useState('');

  function toggle(index: number) {
    const next = checked.includes(index) ? checked.filter(item => item !== index) : [...checked, index];
    setChecked(next);
    try { localStorage.setItem(KEY, JSON.stringify(next)); } catch { /* This tab still keeps the checklist in memory. */ }
  }

  function downloadResult() {
    const text = `# Transcript Review Studio — manual acceptance\n\nDate: ${new Date().toISOString()}\nWorkspace: isolated public-media practice\nSelf-reported checks: ${checked.length}/${steps.length}\nDecision: ${checked.length === steps.length ? 'Ready for owner review; not automatic release approval' : 'Incomplete — do not release yet'}\n\n${steps.map(([title], index) => `- [${checked.includes(index) ? 'x' : ' '}] ${title}`).join('\n')}\n\n## Tester notes\n${notes || 'No notes entered.'}\n\nNo transcript or research files are attached to this checklist.\n`;
    const url = URL.createObjectURL(new Blob([text], { type: 'text/markdown;charset=utf-8' }));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'manual-acceptance.md'; anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return <section className="practice-guide" aria-label="Guided acceptance test">
      <div className="practice-summary"><div><strong>Your first transcript, step by step</strong><p>Public sample · separate practice data · your research projects are not used here.</p></div><button type="button" className="secondary-button" aria-expanded={open} aria-controls="practice-checklist" onClick={() => setOpen(value => !value)}>{open ? 'Hide guide' : 'Show guide'}</button></div>
    {open && <div id="practice-checklist">
      <div className="guide-switch" role="group" aria-label="Practice guide section"><button type="button" aria-pressed={section === 'learn'} onClick={() => setSection('learn')}>Getting started</button><button type="button" aria-pressed={section === 'test'} onClick={() => setSection('test')}>Acceptance checklist · {checked.length}/{steps.length}</button></div>
      {section === 'learn' ? <div className="beginner-guide">
        <ol className="beginner-steps">
          <li><strong>1. Listen & compare</strong><p>Open the sample below and press <b>Play cue</b>. Use <b>Loop cue</b> or 0.75× speed. The source contains a deliberate <code>[practice-error]</code>; compare it with STT A and B while listening.</p><button type="button" className="plain-button" onClick={() => { onNavigate('review'); setOpen(false); }}>Open the review workspace</button></li>
          <li><strong>2. Edit & decide</strong><p>Click <b>Use</b> beside a candidate, then edit the text and enter reviewer initials. <b>Save draft</b> keeps it pending; <b>Mark unclear</b> leaves a question; <b>Save & next</b> is only for words you have checked by listening.</p><p>Revisit your work using <b>Browse → Verified segments</b>. Both machine passes use the same model and can share an error.</p></li>
          <li><strong>3. Export & inspect</strong><p>Download a draft package, then inspect its DOCX, XLSX, and English change log. You can export before finishing all sample cues. Original media is excluded by default; transcript content is still included.</p><button type="button" className="plain-button" onClick={() => { onNavigate('export'); setOpen(false); }}>See the export options</button></li>
        </ol>
        <div className="practice-footer"><span>The sample video is bundled in <code>samples/lua-workshop</code>.</span><a className="secondary-button" href={`${apiBase()}/api/practice/sample`}>Save a copy of the sample</a><button type="button" className="secondary-button" onClick={() => { onNavigate('import'); setOpen(false); }}>Try importing it yourself</button></div>
      </div> : <>
      <p className="practice-intro">Allow about 15 minutes, plus local model processing. Check a box only after you have tested it. This is your acceptance record, not an automated pass.</p>
      <ol className="practice-steps">{steps.map(([title, detail], index) => <li key={title}><label><input type="checkbox" checked={checked.includes(index)} onChange={() => toggle(index)} /><span><strong>{index + 1}. {title}</strong><small>{detail}</small></span></label></li>)}</ol>
      <label className="practice-notes">Anything that felt wrong or confusing?<textarea value={notes} onChange={event => setNotes(event.target.value)} placeholder="Note the step, what you expected, and what happened. Do not paste private research data." /></label>
      <div className="practice-footer"><span>{checked.length} of {steps.length} checks completed</span><a className="secondary-button" href={`${apiBase()}/api/practice/sample`}>Download public sample</a><button type="button" className="primary-button" onClick={downloadResult}>Download my test record</button></div>
      </>}
      <p className="sample-credit">Sample: <a href="https://commons.wikimedia.org/wiki/File:Preliminary_discussions_regarding_Lua_bot_framework.webm" target="_blank" rel="noreferrer">Preliminary discussions regarding Lua bot framework</a>, Jim Carter, <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noreferrer">CC BY-SA 4.0</a>. Video unmodified; the machine-generated practice baseline has seeded wording changes. No speaker identities or transcript accuracy are certified.</p>
    </div>}
  </section>;
}
