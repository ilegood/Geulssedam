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
  hangul_jamo: '약 35~50분',
  latin_hangul_jamo: '약 50~70분',
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
          영문만 가볍게 테스트하거나, 기본 자모(ㄱ~ㅎ, ㅏ~ㅣ)와 6-2-2벌 조합형으로 한글 전체를
          만들어 볼 수 있어요.
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
                  {preset.id === 'latin_hangul_jamo' && <span className="pill">추천</span>}
                </div>
                <p className="preset-desc">{preset.description}</p>
                <div className="preset-meta">
                  <span>총 {preset.total_chars}칸</span>
                  <span>{preset.total_pages}페이지</span>
                  <span>{ESTIMATED_MINUTES[preset.id] || '약 30분'}</span>
                </div>
              </button>
            );
          })}
        </div>
      )}

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
