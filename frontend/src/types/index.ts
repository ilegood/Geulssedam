/** 백엔드 헬스체크 응답 타입 */
export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  task_backend: string;
  template_version: string;
  template_page_px: [number, number];
}

export type Severity = 'ok' | 'warning' | 'error';
export type CellStatus = 'ok' | 'warning' | 'error' | 'empty' | 'unused';
export type JobStatus = 'queued' | 'running' | 'completed' | 'failed';

export interface TemplatePreset {
  id: string;
  name: string;
  description: string;
  stage: string;
  total_pages: number;
  total_chars: number;
}

export interface PresetListResponse {
  template_version: string;
  presets: TemplatePreset[];
}

export interface ValidationIssue {
  code: string;
  severity: 'warning' | 'error';
  message: string;
}

export interface CellMetrics {
  opaque_ratio: number;
  semitransparent_ratio: number;
  estimated_stroke_ratio: number;
  edge_contact_pixels: number;
}

export interface CellValidationResult {
  index: number;
  row: number;
  col: number;
  char: string | null;
  codepoint: string | null;
  status: CellStatus;
  issues: ValidationIssue[];
  metrics: CellMetrics | null;
}

export interface FileValidationResult {
  status: Severity;
  width_px: number | null;
  height_px: number | null;
  cell_width_px: number | null;
  cell_height_px: number | null;
  has_alpha: boolean;
  image_format: string | null;
  issues: ValidationIssue[];
}

export interface ValidationSummary {
  total_cells: number;
  assigned_cells: number;
  ok_count: number;
  warning_count: number;
  error_count: number;
  empty_count: number;
}

export interface UploadValidationResponse {
  session_token: string | null;
  template_version: string;
  preset_id: string;
  page_number: number;
  overall_status: Severity;
  saved: boolean;
  file_validation: FileValidationResult;
  summary: ValidationSummary | null;
  cells: CellValidationResult[];
}

export interface UploadedPageSummary {
  page_number: number;
  overall_status: Severity;
  summary: ValidationSummary | null;
}

export interface SessionInfoResponse {
  session_token: string;
  preset_id: string;
  template_version: string;
  created_at: string;
  expires_at: string;
  uploaded_pages: UploadedPageSummary[];
}

export interface FontBuildRequest {
  session_token: string;
  font_name: string;
  author_name: string;
  letter_spacing: number;
  scale_factor: number;
}

export interface FontBuildArtifacts {
  ttf_filename: string;
  woff2_filename: string;
  zip_filename: string;
  preview_woff2_url: string;
  download_ttf_url: string;
  download_woff2_url: string;
  download_zip_url: string;
  included_chars: string[];
  missing_chars: string[];
}

export interface FontBuildJobResponse {
  job_id: string;
  session_token: string;
  status: JobStatus;
  progress: number;
  message: string;
  created_at: string;
  updated_at: string;
  error: string | null;
  artifacts: FontBuildArtifacts | null;
}

export interface GlyphPreviewItem {
  data_url: string;
  width_em: number;
  height_em: number;
  ascent_em: number;
}

export interface GlyphPreviewResponse {
  session_token: string;
  units_per_em: number;
  default_side_bearing: number;
  glyphs: Record<string, GlyphPreviewItem>;
}
