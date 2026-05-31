export type VideoSlot = "A" | "B";
export type Platform = "youtube" | "instagram" | "unknown";

export interface VideoMetadata {
  video_id: VideoSlot;
  platform: Platform;
  url: string;
  title: string;
  creator: string;
  creator_url?: string | null;
  follower_count: number;
  thumbnail: string | null;
  views: number;
  likes: number | null;
  comments: number | null;
  duration_seconds: number;
  upload_date: string | null;
  hashtags: string[];
  engagement_rate: number;
  transcript_available: boolean;
  chunk_count: number;
}

export interface ComparisonInsights {
  winner: VideoSlot | null;
  engagement_delta: number;
  headline_insights: string[];
  hook_a: string;
  hook_b: string;
  cta_a: boolean;
  cta_b: boolean;
  strategist_summary: string;
  recommendations: string[];
  ai_pending: boolean;
  ai_error: string;
}

export interface AnalysisSnapshot {
  analysis_id: string;
  videos: Record<VideoSlot, VideoMetadata>;
  comparison: ComparisonInsights;
}

export interface Citation {
  video_id: VideoSlot;
  chunk_index: number;
  timestamp: string;
  source_platform: Platform;
  snippet: string;
}

export interface TranscriptLine {
  start: number;
  timestamp: string;
  text: string;
}

export interface VideoTranscript {
  video_id: VideoSlot;
  platform: Platform;
  available: boolean;
  segments: TranscriptLine[];
}

export interface TranscriptResponse {
  analysis_id: string;
  whisper_enabled: boolean;
  transcripts: Record<VideoSlot, VideoTranscript>;
}

export interface VisualFrame {
  start: number;
  timestamp: string;
  ocr_text: string;
}

export interface VideoVisual {
  video_id: VideoSlot;
  platform: Platform;
  available: boolean;
  frames: VisualFrame[];
  visual_summary: string;
  on_screen_text: string;
}

export interface VisualResponse {
  analysis_id: string;
  enabled: boolean;
  vision_enabled: boolean;
  visuals: Record<VideoSlot, VideoVisual>;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  streaming?: boolean;
}
