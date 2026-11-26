import { useEffect, useState } from 'react';
import { fetchFontBuildJob, fetchGlyphPreviews, startFontBuild } from '../api/client';
import type { FontBuildJobResponse, GlyphPreviewResponse } from '../types';

interface BuildStepProps {
  sessionToken: string;
  onBuildSuccess: (job: FontBuildJobResponse) => void;
  onPrev: () => void;
}

const PREVIEW_EM_PX = 68;
const SLOT_HEIGHT_PX = Math.round(PREVIEW_EM_PX * 1.45);
const BASELINE_Y_PX = Math.round(PREVIEW_EM_PX * 1.05);

function pickDefaultPreviewText(glyphKeys: string[]): string {
  const keySet = new Set(glyphKeys);
  const candidates = [
    'Hello World 123',
    '가나다라 마바사',
    'The quick brown fox',
    'ABCDEFG abcdefg 0123',
  ];
  for (const sample of candidates) {
    const nonSpace = [...sample].filter((ch) => ch !== ' ');
    const matched = nonSpace.filter((ch) => keySet.has(ch)).length;
    if (matched >= Math.min(4, nonSpace.length)) {
      return sample;
    }
  }
  return glyphKeys.slice(0, 16).join('') || 'Hello World 123';
}

export function BuildStep({ sessionToken, onBuildSuccess, onPrev }: BuildStepProps) {
  const [fontName, setFontName] = useState<string>('MyHandwriting');
  const [authorName, setAuthorName] = useState<string>('Geulssedam User');
  const [letterSpacing, setLetterSpacing] = useState<number>(0);
  const [scaleFactor, setScaleFactor] = useState<number>(1.0);
  const [agreedTerms, setAgreedTerms] = useState<boolean>(false);

  const [previewData, setPreviewData] = useState<GlyphPreviewResponse | null>(null);
  const [previewLoading, setPreviewLoading] = useState<boolean>(true);
  const [previewText, setPreviewText] = useState<string>('Hello World 123');
  const [showBaseline, setShowBaseline] = useState<boolean>(true);

  const [job, setJob] = useState<FontBuildJobResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState<boolean>(false);

  useEffect(() => {
    let cancelled = false;
    setPreviewLoading(true);
    fetchGlyphPreviews(sessionToken)
      .then((data) => {
        if (cancelled) return;
        setPreviewData(data);
        const keys = Object.keys(data.glyphs);
        if (keys.length > 0) {
          setPreviewText(pickDefaultPreviewText(keys));
        }
      })
      .catch(() => {
        if (!cancelled) {
          setPreviewData(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setPreviewLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [sessionToken]);

  useEffect(() => {
    if (!job || job.status === 'completed' || job.status === 'failed') {
      return;
    }
    const timer = window.setInterval(async () => {
      try {
        const latest = await fetchFontBuildJob(job.job_id);
        setJob(latest);
        if (latest.status === 'completed') {
          onBuildSuccess(latest);
        }
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : '진행률 조회에 실패했습니다.');
      }
    }, 800);

    return () => window.clearInterval(timer);
  }, [job, onBuildSuccess]);

  async function handleStartBuild() {
    setSubmitting(true);
    setError(null);
    try {
      const created = await startFontBuild({
        session_token: sessionToken,
        font_name: fontName.trim() || 'MyHandwriting',
        author_name: authorName.trim() || 'Geulssedam User',
        letter_spacing: letterSpacing,
        scale_factor: scaleFactor,
      });
      setJob(created);
      if (created.status === 'completed') {
        onBuildSuccess(created);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '폰트 생성 요청 중 오류가 발생했습니다.');
    } finally {
      setSubmitting(false);
    }
  }

  const isBuilding =
    submitting || (job !== null && (job.status === 'queued' || job.status === 'running'));

  return (
    <section className="card">
      <div className="step-header">
        <span className="step-badge">4단계</span>
        <h2>폰트 설정 및 생성</h2>
        <p className="muted">
          폰트 이름과 자간·크기를 조절한 뒤 TTF/WOFF2 폰트 파일을 생성합니다.
        </p>
      </div>

      <div className="form-grid">
        <label className="form-field">
          <span>폰트 이름 (영문 권장)</span>
          <input
            type="text"
            value={fontName}
            maxLength={40}
            onChange={(e) => setFontName(e.target.value)}
            placeholder="예: JiminHand"
            disabled={isBuilding}
          />
        </label>

        <label className="form-field">
          <span>제작자 이름</span>
          <input
            type="text"
            value={authorName}
            maxLength={40}
            onChange={(e) => setAuthorName(e.target.value)}
            placeholder="예: 홍길동"
            disabled={isBuilding}
          />
        </label>

        <label className="form-field">
          <span>전체 자간 조절: {letterSpacing > 0 ? `+${letterSpacing}` : letterSpacing}</span>
          <input
            type="range"
            min={-100}
            max={250}
            step={10}
            value={letterSpacing}
            onChange={(e) => setLetterSpacing(Number(e.target.value))}
            disabled={isBuilding}
          />
        </label>

        <label className="form-field">
          <span>글자 크기 보정: {scaleFactor.toFixed(2)}x</span>
          <input
            type="range"
            min={0.7}
            max={1.4}
            step={0.05}
            value={scaleFactor}
            onChange={(e) => setScaleFactor(Number(e.target.value))}
            disabled={isBuilding}
          />
        </label>
      </div>

      <div className="live-preview-box">
        <div className="live-preview-header">
          <div>
            <strong>실시간 자간·크기 미리보기</strong>
            <span className="muted" style={{ marginLeft: 8, fontSize: '0.84rem' }}>
              슬라이더를 움직이면 업로드한 내 손글씨로 바로 반영돼요
            </span>
          </div>
          <div className="row-actions">
            <label className="checkbox-row" style={{ margin: 0, fontSize: '0.84rem' }}>
              <input
                type="checkbox"
                checked={showBaseline}
                onChange={(e) => setShowBaseline(e.target.checked)}
              />
              <span>베이스라인</span>
            </label>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => {
                setLetterSpacing(0);
                setScaleFactor(1.0);
              }}
              disabled={isBuilding || (letterSpacing === 0 && scaleFactor === 1.0)}
            >
              기본값 복원
            </button>
          </div>
        </div>

        <input
          type="text"
          className="live-preview-input"
          value={previewText}
          onChange={(e) => setPreviewText(e.target.value)}
          placeholder="미리볼 문장을 입력해 보세요 (예: Hello World 123)"
        />

        <div className="live-preview-stage" aria-label="손글씨 자간·크기 실시간 미리보기">
          {previewLoading ? (
            <p className="muted" style={{ margin: '24px 0' }}>
              업로드한 손글씨 미리보기를 준비하는 중...
            </p>
          ) : !previewData || Object.keys(previewData.glyphs).length === 0 ? (
            <p className="muted" style={{ margin: '24px 0' }}>
              미리볼 수 있는 글자가 아직 없습니다. 이전 단계에서 템플릿 PNG를 업로드해 주세요.
            </p>
          ) : (
            <div className="live-preview-line" style={{ minHeight: SLOT_HEIGHT_PX }}>
              {showBaseline && (
                <div className="live-preview-baseline" style={{ top: BASELINE_Y_PX }} />
              )}
              {[...previewText].map((ch, idx) => {
                const pxPerEm = PREVIEW_EM_PX / previewData.units_per_em;
                if (ch === ' ') {
                  const spaceW = Math.max(180, 320 + letterSpacing) * pxPerEm;
                  return (
                    <span
                      key={`sp-${idx}`}
                      className="live-glyph-slot"
                      style={{ width: spaceW, height: SLOT_HEIGHT_PX }}
                    />
                  );
                }

                const item = previewData.glyphs[ch];
                if (!item) {
                  return (
                    <span
                      key={`miss-${idx}`}
                      className="live-glyph-missing"
                      title="업로드된 템플릿에 없는 글자"
                    >
                      {ch}
                    </span>
                  );
                }

                const halfDelta = Math.trunc(letterSpacing / 2);
                const lsb = Math.max(10, previewData.default_side_bearing + halfDelta);
                const rsb = Math.max(
                  10,
                  previewData.default_side_bearing + letterSpacing - halfDelta,
                );
                const glyphW = Math.max(1, item.width_em * scaleFactor);
                const glyphH = Math.max(1, item.height_em * scaleFactor);
                const advanceW = Math.max(120, glyphW + lsb + rsb);

                return (
                  <span
                    key={`g-${idx}`}
                    className="live-glyph-slot"
                    style={{
                      width: advanceW * pxPerEm,
                      height: SLOT_HEIGHT_PX,
                    }}
                  >
                    <img
                      src={item.data_url}
                      alt={ch}
                      draggable={false}
                      className="live-glyph-img"
                      style={{
                        left: lsb * pxPerEm,
                        top: BASELINE_Y_PX - item.ascent_em * scaleFactor * pxPerEm,
                        width: glyphW * pxPerEm,
                        height: glyphH * pxPerEm,
                      }}
                    />
                  </span>
                );
              })}
            </div>
          )}
        </div>
      </div>

      <div className="policy-box">
        <strong>권리 및 이용 약관 확인</strong>
        <ul>
          <li>직접 작성한 손글씨와 생성된 폰트의 권리는 사용자 본인에게 귀속됩니다.</li>
          <li>생성된 폰트는 개인적·상업적 용도 모두 자유롭게 사용할 수 있습니다.</li>
          <li>타인의 폰트나 저작물을 무단으로 베껴 업로드하는 행위는 금지됩니다.</li>
          <li>업로드된 원본 이미지는 7일 후 자동으로 삭제됩니다.</li>
        </ul>
        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={agreedTerms}
            onChange={(e) => setAgreedTerms(e.target.checked)}
            disabled={isBuilding}
          />
          <span>본인이 직접 작성한 글씨이며 위 안내에 동의합니다.</span>
        </label>
      </div>

      {job && (
        <div className="progress-box">
          <div className="progress-top">
            <strong>{job.message}</strong>
            <span>{job.progress}%</span>
          </div>
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${job.progress}%` }} />
          </div>
          {job.status === 'failed' && job.error && (
            <p className="error-text">오류 상세: {job.error}</p>
          )}
        </div>
      )}

      {error && <div className="alert alert-error">{error}</div>}

      <div className="step-actions">
        <button type="button" className="btn btn-secondary" onClick={onPrev} disabled={isBuilding}>
          ← 검증 결과로 돌아가기
        </button>
        <button
          type="button"
          className="btn btn-primary"
          onClick={handleStartBuild}
          disabled={isBuilding || !agreedTerms}
        >
          {isBuilding ? '폰트 생성 중...' : '내 손글씨 폰트 생성하기'}
        </button>
      </div>
    </section>
  );
}
