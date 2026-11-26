import type {
  FontBuildJobResponse,
  FontBuildRequest,
  HealthResponse,
  PresetListResponse,
  SessionInfoResponse,
  UploadValidationResponse,
} from '../types';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/** 상대 API 경로를 절대 URL로 변환합니다. */
export function resolveApiUrl(path: string): string {
  if (path.startsWith('http://') || path.startsWith('https://')) {
    return path;
  }
  return `${API_BASE_URL}${path}`;
}

/** 백엔드 서버 상태를 조회합니다. */
export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/health`);
  if (!response.ok) {
    throw new Error(`서버 상태 확인에 실패했습니다. (HTTP ${response.status})`);
  }
  return (await response.json()) as HealthResponse;
}

/** 문자 범위 프리셋 목록을 조회합니다. */
export async function fetchPresets(): Promise<PresetListResponse> {
  const response = await fetch(`${API_BASE_URL}/api/templates/presets`);
  if (!response.ok) {
    throw new Error(`문자 범위 목록을 불러오지 못했습니다. (HTTP ${response.status})`);
  }
  return (await response.json()) as PresetListResponse;
}

/** 비회원 임시 세션을 생성합니다. */
export async function createSession(
  presetId: string,
  templateVersion = 'v1',
): Promise<SessionInfoResponse> {
  const response = await fetch(`${API_BASE_URL}/api/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ preset_id: presetId, template_version: templateVersion }),
  });
  if (!response.ok) {
    const err = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(err?.detail || '임시 세션 생성에 실패했습니다.');
  }
  return (await response.json()) as SessionInfoResponse;
}

/** 기존 임시 세션 정보를 조회합니다. */
export async function fetchSession(sessionToken: string): Promise<SessionInfoResponse> {
  const response = await fetch(`${API_BASE_URL}/api/sessions/${encodeURIComponent(sessionToken)}`);
  if (!response.ok) {
    const err = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(err?.detail || '세션을 찾을 수 없거나 만료되었습니다.');
  }
  return (await response.json()) as SessionInfoResponse;
}

/** 템플릿 다운로드 URL을 생성합니다. */
export function getTemplateDownloadUrl(
  presetId: string,
  kind: 'zip' | 'pdf' | 'canvas' | 'guide' | 'meta',
  page = 1,
): string {
  const query = kind === 'canvas' || kind === 'guide' ? `?page=${page}` : '';
  return `${API_BASE_URL}/api/templates/${encodeURIComponent(presetId)}/download/${kind}${query}`;
}

/** 실험용 한글 조합형(6-2-2벌) 테스트 템플릿 다운로드 URL을 생성합니다. */
export function getJamoTemplateDownloadUrl(
  kind: 'zip' | 'pdf' | 'canvas' | 'guide' | 'meta',
  page = 1,
): string {
  const query = kind === 'canvas' || kind === 'guide' ? `?page=${page}` : '';
  return `${API_BASE_URL}/api/templates/jamo/download/${kind}${query}`;
}

/** 템플릿 PNG 파일을 업로드하고 파일·칸 단위 검증 결과를 반환합니다. */
export async function uploadTemplatePage(params: {
  file: File;
  presetId: string;
  pageNumber: number;
  templateVersion?: string;
  sessionToken?: string | null;
}): Promise<UploadValidationResponse> {
  const formData = new FormData();
  formData.append('file', params.file);
  formData.append('preset_id', params.presetId);
  formData.append('page_number', String(params.pageNumber));
  formData.append('template_version', params.templateVersion || 'v1');
  if (params.sessionToken) {
    formData.append('session_token', params.sessionToken);
  }

  const response = await fetch(`${API_BASE_URL}/api/uploads`, {
    method: 'POST',
    body: formData,
  });

  // 422 응답은 파일 단위 검증 실패지만 구조화된 UploadValidationResponse를 그대로 반환
  if (response.status === 422) {
    return (await response.json()) as UploadValidationResponse;
  }

  if (!response.ok) {
    const err = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(err?.detail || `업로드에 실패했습니다. (HTTP ${response.status})`);
  }

  return (await response.json()) as UploadValidationResponse;
}

/** 비동기 폰트 빌드 작업을 시작합니다. */
export async function startFontBuild(payload: FontBuildRequest): Promise<FontBuildJobResponse> {
  const response = await fetch(`${API_BASE_URL}/api/fonts/build`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const err = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(err?.detail || '폰트 생성 요청에 실패했습니다.');
  }
  return (await response.json()) as FontBuildJobResponse;
}

/** 폰트 빌드 작업 상태 및 진행률을 조회합니다. */
export async function fetchFontBuildJob(jobId: string): Promise<FontBuildJobResponse> {
  const response = await fetch(`${API_BASE_URL}/api/fonts/jobs/${encodeURIComponent(jobId)}`);
  if (!response.ok) {
    const err = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(err?.detail || '작업 상태 조회에 실패했습니다.');
  }
  return (await response.json()) as FontBuildJobResponse;
}
