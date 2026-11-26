import { useEffect, useMemo, useState } from 'react';
import { resolveApiUrl } from '../api/client';
import type { FontBuildJobResponse } from '../types';

interface PreviewDownloadStepProps {
  job: FontBuildJobResponse;
  onRebuild: () => void;
}

const SAMPLE_SENTENCES = [
  { label: '영문 팬그램', text: 'The quick brown fox jumps over the lazy dog. 0123456789' },
  { label: '한글 인사', text: '안녕하세요! 오늘 하루도 좋은 일만 가득하길 바라요.' },
  { label: '한글·영문 혼합', text: '글씨담 Geulssedam 2026 — 내 손글씨를 폰트에 담다!' },
];

export function PreviewDownloadStep({ job, onRebuild }: PreviewDownloadStepProps) {
  const artifacts = job.artifacts;
  const [sampleText, setSampleText] = useState<string>(SAMPLE_SENTENCES[2].text);
  const [fontSize, setFontSize] = useState<number>(40);
  const [letterSpacingPx, setLetterSpacingPx] = useState<number>(0);
  const [lineHeight, setLineHeight] = useState<number>(1.5);
  const [darkMode, setDarkMode] = useState<boolean>(false);
  const [fontLoaded, setFontLoaded] = useState<boolean>(false);
  const [fontError, setFontError] = useState<string | null>(null);

  const previewFamily = useMemo(() => `GeulssedamPreview_${job.job_id}`, [job.job_id]);

  useEffect(() => {
    if (!artifacts) return;
    let cancelled = false;
    const url = `${resolveApiUrl(artifacts.preview_woff2_url)}?t=${Date.now()}`;
    const face = new FontFace(previewFamily, `url(${url})`);

    face
      .load()
      .then((loaded) => {
        if (cancelled) return;
        document.fonts.add(loaded);
        setFontLoaded(true);
        setFontError(null);
      })
      .catch(() => {
        if (cancelled) return;
        setFontError('미리보기 폰트를 불러오지 못했습니다. 파일을 직접 다운로드해 확인해 주세요.');
      });

    return () => {
      cancelled = true;
      document.fonts.delete(face);
    };
  }, [artifacts, previewFamily]);

  const includedSet = useMemo(
    () => new Set([...(artifacts?.included_chars ?? []), ' ', '\n', '\t']),
    [artifacts],
  );

  // 입력 문장 중 생성된 폰트에 없는(미작성) 글자 추출
  const missingInInput = useMemo(() => {
    const found = new Set<string>();
    for (const ch of sampleText) {
      if (!includedSet.has(ch)) {
        found.add(ch);
      }
    }
    return Array.from(found);
  }, [sampleText, includedSet]);

  if (!artifacts) {
    return null;
  }

  return (
    <section className="card">
      <div className="step-header">
        <span className="step-badge">5단계</span>
        <h2>내 손글씨 폰트 미리보기 & 다운로드</h2>
        <p className="muted">
          총 <strong>{artifacts.included_chars.length}자</strong>가 포함된 폰트가 완성되었어요!
          원하는 문장을 입력해 바로 확인해 보세요.
        </p>
      </div>

      <div className="sample-buttons">
        {SAMPLE_SENTENCES.map((item) => (
          <button
            key={item.label}
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => setSampleText(item.text)}
          >
            {item.label}
          </button>
        ))}
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={() => setDarkMode((prev) => !prev)}
        >
          {darkMode ? '라이트 배경' : '다크 배경'}
        </button>
      </div>

      <div className="preview-controls">
        <label>
          <span>크기 ({fontSize}px)</span>
          <input
            type="range"
            min={16}
            max={96}
            value={fontSize}
            onChange={(e) => setFontSize(Number(e.target.value))}
          />
        </label>
        <label>
          <span>자간 ({letterSpacingPx}px)</span>
          <input
            type="range"
            min={-4}
            max={20}
            value={letterSpacingPx}
            onChange={(e) => setLetterSpacingPx(Number(e.target.value))}
          />
        </label>
        <label>
          <span>줄 간격 ({lineHeight.toFixed(1)})</span>
          <input
            type="range"
            min={1.1}
            max={2.4}
            step={0.1}
            value={lineHeight}
            onChange={(e) => setLineHeight(Number(e.target.value))}
          />
        </label>
      </div>

      <textarea
        className="preview-input"
        rows={3}
        value={sampleText}
        onChange={(e) => setSampleText(e.target.value)}
        placeholder="미리보기할 문장을 입력해 보세요..."
      />

      {fontError && <div className="alert alert-warning">{fontError}</div>}

      <div
        className={`preview-stage ${darkMode ? 'dark' : 'light'}`}
        style={{
          fontFamily: fontLoaded ? `"${previewFamily}", sans-serif` : 'sans-serif',
          fontSize: `${fontSize}px`,
          letterSpacing: `${letterSpacingPx}px`,
          lineHeight,
        }}
      >
        {sampleText || '문장을 입력하면 내 손글씨로 표시됩니다.'}
      </div>

      {missingInInput.length > 0 && (
        <div className="missing-box">
          <strong>입력한 문장에 미작성 글자가 있어요 ({missingInInput.length}자)</strong>
          <p className="muted">
            아래 글자는 아직 그리지 않아 기본 시스템 글꼴로 표시됩니다.
          </p>
          <div className="missing-chips">
            {missingInInput.map((ch) => (
              <span key={ch} className="missing-chip">
                {ch}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="download-panel">
        <h3>폰트 다운로드</h3>
        <div className="download-buttons">
          <a
            className="btn btn-primary"
            href={resolveApiUrl(artifacts.download_zip_url)}
            download={artifacts.zip_filename}
          >
            전체 패키지 ZIP 다운로드 (TTF + WOFF2 + 라이선스)
          </a>
          <a
            className="btn btn-secondary"
            href={resolveApiUrl(artifacts.download_ttf_url)}
            download={artifacts.ttf_filename}
          >
            TTF 다운로드
          </a>
          <a
            className="btn btn-secondary"
            href={resolveApiUrl(artifacts.download_woff2_url)}
            download={artifacts.woff2_filename}
          >
            WOFF2 다운로드
          </a>
        </div>
      </div>

      <div className="guide-box">
        <h3>설치 및 사용 안내</h3>
        <ul>
          <li>
            <strong>Windows</strong>: 압축을 푼 뒤 <code>.ttf</code> 파일을 더블 클릭해 [설치]를
            누르세요.
          </li>
          <li>
            <strong>macOS</strong>: <code>.ttf</code> 파일을 더블 클릭해 서체 관리자에서 [서체
            설치]를 누르세요.
          </li>
          <li>
            <strong>라이선스</strong>: 본인이 직접 그린 손글씨 폰트는 개인·상업 용도 모두 자유롭게
            사용할 수 있어요.
          </li>
        </ul>
      </div>

      <div className="step-actions">
        <button type="button" className="btn btn-secondary" onClick={onRebuild}>
          ← 자간·크기 다시 조절해 재생성
        </button>
      </div>
    </section>
  );
}
