import { useEffect, useState } from 'react';
import { fetchHealth } from './api/client';
import type { HealthResponse } from './types';

function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchHealth()
      .then((data) => {
        setHealth(data);
        setError(null);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : '백엔드 서버에 연결할 수 없습니다.');
      });
  }, []);

  return (
    <main className="container">
      <header className="hero">
        <h1>글씨담 (Geulssedam)</h1>
        <p>
          내 손글씨를 폰트에 담다 — 템플릿에 글자를 그려 투명 PNG로 올리면 TTF/WOFF2 폰트로
          변환해 드립니다.
        </p>
      </header>

      <section className="status-card">
        <h2>개발 환경 상태</h2>
        {health ? (
          <ul>
            <li>백엔드 상태: 정상 ({health.status})</li>
            <li>템플릿 규격 버전: {health.template_version}</li>
            <li>
              표준 페이지 해상도: {health.template_page_px[0]} × {health.template_page_px[1]} px
            </li>
            <li>비동기 작업 모드: {health.task_backend}</li>
          </ul>
        ) : error ? (
          <p className="error">백엔드 미연결: {error}</p>
        ) : (
          <p>백엔드 상태를 확인하는 중...</p>
        )}
      </section>
    </main>
  );
}

export default App;
