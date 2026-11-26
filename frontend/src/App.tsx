import { useCallback, useEffect, useState } from 'react';
import { createSession, fetchPresets, fetchSession } from './api/client';
import { BuildStep } from './components/BuildStep';
import { PreviewDownloadStep } from './components/PreviewDownloadStep';
import { ScopeStep } from './components/ScopeStep';
import { TemplateStep } from './components/TemplateStep';
import { UploadValidateStep } from './components/UploadValidateStep';
import type {
  FontBuildJobResponse,
  TemplatePreset,
  UploadValidationResponse,
} from './types';

type StepNumber = 1 | 2 | 3 | 4 | 5;

const STEPS: { num: StepNumber; label: string }[] = [
  { num: 1, label: '범위 선택' },
  { num: 2, label: '템플릿 받기' },
  { num: 3, label: '업로드 · 검증' },
  { num: 4, label: '폰트 생성' },
  { num: 5, label: '미리보기 · 다운로드' },
];

function App() {
  const [step, setStep] = useState<StepNumber>(1);
  const [presets, setPresets] = useState<TemplatePreset[]>([]);
  const [templateVersion, setTemplateVersion] = useState<string>('v1');
  const [selectedPresetId, setSelectedPresetId] = useState<string>('mvp');
  const [loadingPresets, setLoadingPresets] = useState<boolean>(true);
  const [globalError, setGlobalError] = useState<string | null>(null);

  const [sessionToken, setSessionToken] = useState<string | null>(null);
  const [copiedLink, setCopiedLink] = useState<boolean>(false);
  const [validationsByPage, setValidationsByPage] = useState<
    Record<number, UploadValidationResponse>
  >({});
  const [completedJob, setCompletedJob] = useState<FontBuildJobResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function init() {
      try {
        const data = await fetchPresets();
        if (cancelled) return;
        setPresets(data.presets);
        setTemplateVersion(data.template_version);

        const params = new URLSearchParams(window.location.search);
        const tokenFromUrl = params.get('token');
        if (tokenFromUrl) {
          try {
            const session = await fetchSession(tokenFromUrl);
            if (!cancelled) {
              setSessionToken(session.session_token);
              setSelectedPresetId(session.preset_id);
              setTemplateVersion(session.template_version);
            }
          } catch {
            // 만료되거나 잘못된 토큰은 무시하고 새로 시작
          }
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setGlobalError(
            err instanceof Error ? err.message : '백엔드 서버에 연결할 수 없습니다.',
          );
        }
      } finally {
        if (!cancelled) {
          setLoadingPresets(false);
        }
      }
    }
    void init();
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedPreset =
    presets.find((p) => p.id === selectedPresetId) || presets[0] || null;

  const updateUrlToken = useCallback((token: string) => {
    const url = new URL(window.location.href);
    url.searchParams.set('token', token);
    window.history.replaceState({}, '', url.toString());
  }, []);

  async function handleProceedFromScope() {
    if (!sessionToken) {
      try {
        const session = await createSession(selectedPresetId, templateVersion);
        setSessionToken(session.session_token);
        updateUrlToken(session.session_token);
      } catch (err: unknown) {
        setGlobalError(
          err instanceof Error ? err.message : '임시 세션 발급에 실패했습니다.',
        );
        return;
      }
    }
    setStep(2);
  }

  function handleUploadComplete(pageNumber: number, result: UploadValidationResponse) {
    if (result.session_token && result.session_token !== sessionToken) {
      setSessionToken(result.session_token);
      updateUrlToken(result.session_token);
    }
    setValidationsByPage((prev) => ({
      ...prev,
      [pageNumber]: result,
    }));
  }

  const handleBuildSuccess = useCallback((job: FontBuildJobResponse) => {
    setCompletedJob(job);
    setStep(5);
  }, []);

  function handleCopySessionLink() {
    if (!sessionToken) return;
    const url = new URL(window.location.href);
    url.searchParams.set('token', sessionToken);
    void navigator.clipboard.writeText(url.toString());
    setCopiedLink(true);
    window.setTimeout(() => setCopiedLink(false), 2000);
  }

  const hasSavedUpload = Object.values(validationsByPage).some((item) => item.saved);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand">
            <span className="brand-mark">글</span>
            <div>
              <h1>글씨담 (Geulssedam)</h1>
              <p>내 손글씨를 폰트에 담다</p>
            </div>
          </div>

          {sessionToken && (
            <div className="session-pill">
              <span className="muted">임시 작업 링크</span>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={handleCopySessionLink}
              >
                {copiedLink ? '복사됨!' : '링크 복사'}
              </button>
            </div>
          )}
        </div>
      </header>

      <main className="container">
        <nav className="stepper" aria-label="폰트 제작 단계">
          {STEPS.map((item) => {
            const isActive = step === item.num;
            const isDone = step > item.num;
            const disabled =
              (item.num === 4 && !hasSavedUpload) ||
              (item.num === 5 && !completedJob) ||
              !selectedPreset;
            return (
              <button
                key={item.num}
                type="button"
                className={`step-item ${isActive ? 'active' : ''} ${isDone ? 'done' : ''}`}
                onClick={() => setStep(item.num)}
                disabled={disabled}
              >
                <span className="step-num">{item.num}</span>
                <span className="step-label">{item.label}</span>
              </button>
            );
          })}
        </nav>

        {globalError && <div className="alert alert-error">{globalError}</div>}

        {step === 1 && (
          <ScopeStep
            presets={presets}
            selectedPresetId={selectedPresetId}
            onSelectPreset={(id) => {
              setSelectedPresetId(id);
              setValidationsByPage({});
              setCompletedJob(null);
            }}
            onNext={() => void handleProceedFromScope()}
            loading={loadingPresets}
          />
        )}

        {step === 2 && selectedPreset && (
          <TemplateStep
            preset={selectedPreset}
            templateVersion={templateVersion}
            onPrev={() => setStep(1)}
            onNext={() => setStep(3)}
          />
        )}

        {step === 3 && selectedPreset && (
          <UploadValidateStep
            preset={selectedPreset}
            templateVersion={templateVersion}
            sessionToken={sessionToken}
            validationsByPage={validationsByPage}
            onUploadComplete={handleUploadComplete}
            onPrev={() => setStep(2)}
            onNext={() => setStep(4)}
          />
        )}

        {step === 4 && sessionToken && (
          <BuildStep
            sessionToken={sessionToken}
            onBuildSuccess={handleBuildSuccess}
            onPrev={() => setStep(3)}
          />
        )}

        {step === 5 && completedJob && (
          <PreviewDownloadStep job={completedJob} onRebuild={() => setStep(4)} />
        )}
      </main>

      <footer className="footer">
        <p>
          글씨담 (Geulssedam) · 업로드 이미지는 7일 후 자동 삭제됩니다 · 생성 폰트는 개인·상업
          용도 모두 사용 가능
        </p>
      </footer>
    </div>
  );
}

export default App;
