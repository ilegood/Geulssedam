import { getTemplateDownloadUrl } from '../api/client';
import type { TemplatePreset } from '../types';

interface TemplateStepProps {
  preset: TemplatePreset;
  templateVersion: string;
  onPrev: () => void;
  onNext: () => void;
}

export function TemplateStep({ preset, templateVersion, onPrev, onNext }: TemplateStepProps) {
  const pageNumbers = Array.from({ length: preset.total_pages }, (_, idx) => idx + 1);

  return (
    <section className="card">
      <div className="step-header">
        <span className="step-badge">2단계</span>
        <h2>템플릿을 다운로드해 글자를 그려주세요</h2>
        <p className="muted">
          선택 세트: <strong>{preset.name}</strong> ({preset.total_chars}자 · {preset.total_pages}
          페이지 · 규격 {templateVersion})
        </p>
      </div>

      <div className="download-banner">
        <div>
          <strong>한 번에 전체 템플릿 받기 (ZIP)</strong>
          <p className="muted">
            투명 캔버스 PNG, 가이드 레이어 PNG, 인쇄용 PDF, 좌표 메타데이터 JSON이 모두 들어있어요.
          </p>
        </div>
        <a
          className="btn btn-primary"
          href={getTemplateDownloadUrl(preset.id, 'zip')}
          download
        >
          전체 템플릿 ZIP 다운로드
        </a>
      </div>

      <div className="page-download-list">
        <h3>페이지별 개별 다운로드</h3>
        {pageNumbers.map((page) => (
          <div key={page} className="page-download-row">
            <div>
              <strong>{page}페이지</strong>
              <span className="muted"> · 10×10칸 (5,120×5,120px)</span>
            </div>
            <div className="row-actions">
              <a
                className="btn btn-secondary btn-sm"
                href={getTemplateDownloadUrl(preset.id, 'canvas', page)}
                download
              >
                투명 캔버스 PNG
              </a>
              <a
                className="btn btn-secondary btn-sm"
                href={getTemplateDownloadUrl(preset.id, 'guide', page)}
                download
              >
                가이드 레이어 PNG
              </a>
            </div>
          </div>
        ))}
        <div className="page-download-row">
          <div>
            <strong>인쇄·참고용 PDF</strong>
            <span className="muted"> · 전체 {preset.total_pages}페이지</span>
          </div>
          <a
            className="btn btn-secondary btn-sm"
            href={getTemplateDownloadUrl(preset.id, 'pdf')}
            download
          >
            PDF 다운로드
          </a>
        </div>
      </div>

      <div className="guide-box">
        <h3>예쁘게 나오는 작성 가이드</h3>
        <ul>
          <li>
            <strong>레이어 분리</strong>: 프로크리에이트·클립스튜디오 등에서 가이드 PNG를 아래
            레이어에 두고, 투명 캔버스 레이어에 글자를 그린 뒤 <strong>가이드 레이어를 숨기고</strong>{' '}
            투명 PNG로 내보내 주세요.
          </li>
          <li>
            <strong>브러시와 획 두께</strong>: 번짐·수채화 브러시보다 단단한 단색 브러시를
            권장해요. 획이 너무 얇으면 작은 글씨에서 사라질 수 있어요.
          </li>
          <li>
            <strong>칸 여백과 베이스라인</strong>: 칸 경계에 닿지 않게 안쪽 여백을 두고, 빨간
            베이스라인에 맞춰 그리면 줄맞춤이 깔끔해져요.
          </li>
        </ul>
      </div>

      <div className="step-actions">
        <button type="button" className="btn btn-secondary" onClick={onPrev}>
          ← 범위 다시 선택
        </button>
        <button type="button" className="btn btn-primary" onClick={onNext}>
          다 그렸어요, 업로드하러 가기 →
        </button>
      </div>
    </section>
  );
}
