import { useState, type ChangeEvent, type DragEvent } from 'react';
import { uploadTemplatePage } from '../api/client';
import type {
  CellValidationResult,
  TemplatePreset,
  UploadValidationResponse,
} from '../types';

interface UploadValidateStepProps {
  preset: TemplatePreset;
  templateVersion: string;
  sessionToken: string | null;
  validationsByPage: Record<number, UploadValidationResponse>;
  onUploadComplete: (pageNumber: number, result: UploadValidationResponse) => void;
  onPrev: () => void;
  onNext: () => void;
}

const STATUS_LABELS: Record<string, string> = {
  ok: '정상',
  warning: '경고',
  error: '오류',
  empty: '빈 칸',
  unused: '미사용',
};

export function UploadValidateStep({
  preset,
  templateVersion,
  sessionToken,
  validationsByPage,
  onUploadComplete,
  onPrev,
  onNext,
}: UploadValidateStepProps) {
  const [activePage, setActivePage] = useState<number>(1);
  const [uploading, setUploading] = useState<boolean>(false);
  const [dragOver, setDragOver] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [selectedCell, setSelectedCell] = useState<CellValidationResult | null>(null);

  const pageNumbers = Array.from({ length: preset.total_pages }, (_, idx) => idx + 1);
  const currentResult = validationsByPage[activePage] || null;
  const uploadedSavedCount = Object.values(validationsByPage).filter((item) => item.saved).length;

  async function handleFile(file: File | undefined) {
    if (!file) return;
    setUploading(true);
    setUploadError(null);
    setSelectedCell(null);
    try {
      const result = await uploadTemplatePage({
        file,
        presetId: preset.id,
        pageNumber: activePage,
        templateVersion,
        sessionToken,
      });
      onUploadComplete(activePage, result);
    } catch (err: unknown) {
      setUploadError(err instanceof Error ? err.message : '파일 업로드 중 오류가 발생했습니다.');
    } finally {
      setUploading(false);
    }
  }

  function onFileInputChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    void handleFile(file);
    e.target.value = '';
  }

  function onDrop(e: DragEvent<HTMLLabelElement>) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    void handleFile(file);
  }

  return (
    <section className="card">
      <div className="step-header">
        <span className="step-badge">3단계</span>
        <h2>투명 PNG 업로드 및 칸별 품질 검증</h2>
        <p className="muted">
          페이지를 선택해 업로드하면 해상도·투명 배경·획 두께·잘림·가이드선 잔존 여부를 자동으로
          진단해 드려요.
        </p>
      </div>

      <div className="notice-box">
        <strong>업로드 전 확인해 주세요</strong>
        <ul>
          <li>해상도가 낮으면 곡선이 각져 보이고 획 끝이 뭉개져요.</li>
          <li>칸당 512px 이상을 권장해요. 256px 미만은 업로드할 수 없어요.</li>
          <li>컬러, 그라데이션, 질감은 반영되지 않고 단색 윤곽선만 사용돼요.</li>
        </ul>
      </div>

      <div className="page-tabs">
        {pageNumbers.map((page) => {
          const res = validationsByPage[page];
          const badge = res ? (res.saved ? STATUS_LABELS[res.overall_status] : '거부') : '미업로드';
          return (
            <button
              key={page}
              type="button"
              className={`page-tab ${activePage === page ? 'active' : ''}`}
              onClick={() => {
                setActivePage(page);
                setSelectedCell(null);
              }}
            >
              <span>{page}페이지</span>
              <span className={`mini-badge status-${res ? (res.saved ? res.overall_status : 'error') : 'empty'}`}>
                {badge}
              </span>
            </button>
          );
        })}
      </div>

      <label
        className={`dropzone ${dragOver ? 'drag-over' : ''}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
      >
        <input type="file" accept="image/png" onChange={onFileInputChange} disabled={uploading} />
        {uploading ? (
          <p>
            <strong>{activePage}페이지 이미지를 검증하는 중...</strong>
          </p>
        ) : (
          <>
            <p>
              <strong>{activePage}페이지 투명 PNG</strong>를 이곳에 끌어다 놓거나 클릭해 선택하세요
            </p>
            <span className="muted">권장 5,120×5,120px · 최소 2,560×2,560px · 최대 50MB</span>
          </>
        )}
      </label>

      {uploadError && <div className="alert alert-error">{uploadError}</div>}

      {currentResult && (
        <div className="validation-section">
          <div className={`alert alert-${currentResult.file_validation.status}`}>
            <strong>
              파일 단위 검증: {STATUS_LABELS[currentResult.file_validation.status]}
              {currentResult.file_validation.width_px &&
                ` (${currentResult.file_validation.width_px}×${currentResult.file_validation.height_px}px)`}
            </strong>
            {currentResult.file_validation.issues.length > 0 ? (
              <ul>
                {currentResult.file_validation.issues.map((issue, idx) => (
                  <li key={`${issue.code}-${idx}`}>{issue.message}</li>
                ))}
              </ul>
            ) : (
              <p>규격에 맞는 투명 PNG 파일입니다.</p>
            )}
          </div>

          {currentResult.summary && (
            <>
              <div className="summary-bar">
                <span className="summary-chip status-ok">
                  정상 {currentResult.summary.ok_count}
                </span>
                <span className="summary-chip status-warning">
                  경고 {currentResult.summary.warning_count}
                </span>
                <span className="summary-chip status-error">
                  오류 {currentResult.summary.error_count}
                </span>
                <span className="summary-chip status-empty">
                  빈 칸 {currentResult.summary.empty_count}
                </span>
              </div>

              <p className="muted">각 칸을 클릭하면 상세 진단 메시지와 측정 수치를 볼 수 있어요.</p>

              <div className="cell-grid">
                {currentResult.cells.map((cell) => {
                  const isSelected = selectedCell?.index === cell.index;
                  return (
                    <button
                      key={cell.index}
                      type="button"
                      className={`cell-tile status-${cell.status} ${isSelected ? 'selected' : ''}`}
                      onClick={() => setSelectedCell(cell)}
                      disabled={cell.status === 'unused'}
                      title={cell.char ? `${cell.char} (${STATUS_LABELS[cell.status]})` : '미사용'}
                    >
                      <span className="cell-char">{cell.char ?? '·'}</span>
                      <span className="cell-idx">{cell.index + 1}</span>
                    </button>
                  );
                })}
              </div>

              {selectedCell && (
                <div className="cell-detail">
                  <div className="cell-detail-head">
                    <strong>
                      {selectedCell.index + 1}번 칸 · &lsquo;{selectedCell.char}&rsquo; (
                      {selectedCell.codepoint})
                    </strong>
                    <span className={`mini-badge status-${selectedCell.status}`}>
                      {STATUS_LABELS[selectedCell.status]}
                    </span>
                  </div>
                  {selectedCell.issues.length > 0 ? (
                    <ul>
                      {selectedCell.issues.map((issue, idx) => (
                        <li key={`${issue.code}-${idx}`}>{issue.message}</li>
                      ))}
                    </ul>
                  ) : (
                    <p>문제가 발견되지 않은 깔끔한 글자입니다.</p>
                  )}
                  {selectedCell.metrics && (
                    <div className="metrics-row">
                      <span>
                        채움 비율: {(selectedCell.metrics.opaque_ratio * 100).toFixed(1)}%
                      </span>
                      <span>
                        추정 획 두께: {(selectedCell.metrics.estimated_stroke_ratio * 100).toFixed(1)}
                        %
                      </span>
                      <span>
                        반투명 비율: {(selectedCell.metrics.semitransparent_ratio * 100).toFixed(1)}
                        %
                      </span>
                      <span>경계 접촉: {selectedCell.metrics.edge_contact_pixels}px</span>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}

      <div className="step-actions">
        <button type="button" className="btn btn-secondary" onClick={onPrev}>
          ← 템플릿 다운로드
        </button>
        <button
          type="button"
          className="btn btn-primary"
          onClick={onNext}
          disabled={uploadedSavedCount === 0}
        >
          폰트 설정 및 생성하기 ({uploadedSavedCount}/{preset.total_pages}페이지 업로드됨) →
        </button>
      </div>
    </section>
  );
}
