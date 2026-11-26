import type { HealthResponse } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/** 백엔드 서버 상태를 조회합니다. */
export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/health`);
  if (!response.ok) {
    throw new Error(`서버 상태 확인에 실패했습니다. (HTTP ${response.status})`);
  }
  return (await response.json()) as HealthResponse;
}
