/** 백엔드 헬스체크 응답 타입 */
export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  task_backend: string;
  template_version: string;
  template_page_px: [number, number];
}
