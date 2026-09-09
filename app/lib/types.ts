export type WorkflowView = 'import' | 'review' | 'export';

export type RecordingStatus = 'imported' | 'processing' | 'ready' | 'error';

export interface Capabilities {
  practice_mode: boolean;
  local: boolean;
  platform: string;
  python: string;
  ffmpeg: boolean;
  ffprobe: boolean;
  stt: {
    mlx_whisper: boolean;
    faster_whisper: boolean;
    active: string | null;
    default_model: string;
    note: string;
  };
  speaker_assignment: {
    named_tracks: boolean;
    generic_diarization: boolean;
    generic_diarization_model_detected?: boolean;
    note: string;
  };
  data_directory: string;
}

export interface RecordingMetadata {
  media_type?: 'video' | 'audio';
  video_codec?: string | null;
  audio_codec?: string | null;
  width?: number | null;
  height?: number | null;
  model?: string;
  language?: string;
  dual_pass?: boolean;
  named_speaker_tracks?: string[];
  processing_is_local?: boolean;
}

export interface Recording {
  id: string;
  project_id: string;
  name: string;
  duration_ms: number;
  status: RecordingStatus;
  processing_stage: string;
  processed_percent: number;
  error?: string | null;
  metadata: RecordingMetadata;
  cue_count?: number;
  verified_count?: number;
  flagged_count?: number;
  counts?: { total: number; verified: number; flagged: number };
  speakers?: string[];
}

export interface Project {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  reviewer?: string;
  recordings?: Recording[];
}

export type AmbiguityReason =
  | 'word_disagreement'
  | 'low_confidence'
  | 'speaker_mismatch'
  | 'timing_drift'
  | 'missing_version'
  | 'missing_source';

export interface DiffPart {
  kind: 'equal' | 'changed' | 'removed';
  text: string;
}

export interface Cue {
  revision: number;
  id: number;
  recording_id: string;
  cue_index: number;
  start_ms: number;
  end_ms: number;
  source_text: string;
  stt_a_text: string;
  stt_b_text: string;
  final_text: string;
  speaker: string;
  confidence_a: number | null;
  confidence_b: number | null;
  ambiguity_score: number;
  ambiguity_reasons: AmbiguityReason[];
  status: 'pending' | 'flagged' | 'verified' | 'unclear';
  diff_source_a?: DiffPart[];
  diff_source_b?: DiffPart[];
}
