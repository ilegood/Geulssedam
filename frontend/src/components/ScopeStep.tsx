import { getJamoTemplateDownloadUrl } from '../api/client';
import type { TemplatePreset } from '../types';

interface ScopeStepProps {
  presets: TemplatePreset[];
  selectedPresetId: string;
  onSelectPreset: (presetId: string) => void;
  onNext: () => void;
  loading: boolean;
}

const ESTIMATED_MINUTES: Record<string, string> = {
  latin_basic: '약 15~20분',
  hangul_200: '약 30~40분',
  mvp: '약 45~60분',
};

export function ScopeStep({
  presets,
  selectedPresetId,
  onSelectPreset,
  onNext,
  loading,
}: ScopeStepProps) {
  return (
    <section className="card">
      <div className="step-header">
        <span className="step-badge">1단계</span>
        <h2>만들 문자 범위를 선택해 주세요</h2>
        <p className="muted">
          처음 시작한다면 영문·숫자·특수문자(1페이지)로 가볍게 테스트하거나, MVP 전체(3페이지)로
          한글까지 한 번에 만들어 볼 수 있어요.
        </p>
      </div>

      {loading ? (
        <p className="muted">문자 범위 목록을 불러오는 중...</p>
      ) : (
        <div className="preset-grid">
          {presets.map((preset) => {
            const isSelected = preset.id === selectedPresetId;
            return (
              <button
                key={preset.id}
                type="button"
                className={`preset-card ${isSelected ? 'selected' : ''}`}
                onClick={() => onSelectPreset(preset.id)}
              >
                <div className="preset-top">
                  <strong>{preset.name}</strong>
                  {preset.id === 'mvp' && <span className="pill">추천</span>}
                </div>
                <p className="preset-desc">{preset.description}</p>
                <div className="preset-meta">
                  <span>총 {preset.total_chars}자</span>
                  <span>{preset.total_pages}페이지</span>
                  <span>{ESTIMATED_MINUTES[preset.id] || '약 30분'}</span>
                </div>
              </button>
            );
          })}
        </div>
      )}

      <div className="policy-box">
        <strong>실험용 · 한글 조합형 테스트 템플릿 (6-2-2벌, 210칸 / 3페이지)</strong>
        <p className="muted" style={{ margin: '0.35rem 0 0.75rem' }}>
          한글 11,172자 조합 확장을 미리 테스트해 볼 수 있는 별도 템플릿이에요. 파랑(초성)·초록
          (중성)·주황(종성) 영역에 맞춰 자모만 그려볼 수 있습니다.
        </p>
        <div className="row-actions" style={{ flexWrap: 'wrap' }}>
          <a
            className="btn btn-secondary btn-sm"
            href={getJamoTemplateDownloadUrl('zip')}
            download
          >
            조합형 전체 ZIP 다운로드
          </a>
          <a
            className="btn btn-secondary btn-sm"
            href={getJamoTemplateDownloadUrl('pdf')}
            download
          >
            조합형 PDF 다운로드
          </a>
          <a
            className="btn btn-secondary btn-sm"
            href={getJamoTemplateDownloadUrl('guide', 1)}
            download
          >
            1P 가이드(초성 1~3벌)
          </a>
          <a
            className="btn btn-secondary btn-sm"
            href={getJamoTemplateDownloadUrl('guide', 2)}
            download
          >
            2P 가이드(초성 4~6벌)
          </a>
          <a
            className="btn btn-secondary btn-sm"
            href={getJamoTemplateDownloadUrl('guide', 3)}
            download
          >
            3P 가이드(중·종성)
          </a>
        </div>
      </div>

      <div className="policy-box">
        <strong>안심하고 만들어 보세요</strong>
        <ul>
          <li>회원가입 없이 임시 링크(토큰)만으로 바로 제작할 수 있어요.</li>
          <li>업로드한 손글씨 이미지는 7일 뒤 서버에서 자동 삭제돼요.</li>
          <li>생성된 폰트는 사용자 본인 소유이며, 개인·상업 용도 모두 자유롭게 사용할 수 있어요.</li>
        </ul>
      </div>

      <div className="step-actions">
        <button type="button" className="btn btn-primary" onClick={onNext} disabled={loading}>
          선택한 범위로 템플릿 받기 →
        </button>
      </div>
    </section>
  );
}
