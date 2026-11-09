import React, { useState } from 'react';
import { VerificationReport } from '../hooks/useJohnnyApi';

interface VerificationPanelProps {
  verificationReport: VerificationReport | null;
  runVerification: (checks?: string[]) => Promise<VerificationReport | null>;
}

export const VerificationPanel: React.FC<VerificationPanelProps> = ({
  verificationReport,
  runVerification,
}) => {
  const [isRunning, setIsRunning] = useState(false);

  const handleRunVerification = async () => {
    setIsRunning(true);
    try {
      await runVerification();
    } finally {
      setIsRunning(false);
    }
  };

  const isVerified = verificationReport?.is_verified;
  const confidence = verificationReport?.confidence_score ?? 0.0;

  return (
    <div className="p-4 space-y-6 text-slate-100 bg-slate-900/60 rounded-xl border border-slate-800 backdrop-blur-md">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div>
          <div className="flex items-center gap-2.5">
            <h2 className="text-xl font-bold tracking-tight text-white">Closed-Loop Verification Engine</h2>
            {verificationReport && (
              <span
                className={`px-3 py-0.5 text-xs font-semibold rounded-full border ${
                  isVerified
                    ? 'bg-emerald-950/50 text-emerald-400 border-emerald-800'
                    : 'bg-rose-950/50 text-rose-400 border-rose-800'
                }`}
              >
                {isVerified ? '✅ VERIFIED' : '❌ VERIFICATION FAILED'}
              </span>
            )}
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Closed-loop linting, testing, and system integrity verification pipeline.
          </p>
        </div>

        <button
          onClick={handleRunVerification}
          disabled={isRunning}
          className="px-4 py-2 text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl disabled:opacity-40 transition shadow-md shadow-emerald-900/30"
        >
          {isRunning ? 'Running Checks...' : '⚡ Run Verification Suite'}
        </button>
      </div>

      {/* Verification Score Overview */}
      {verificationReport && (
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-slate-950/80 p-3 rounded-xl border border-slate-800 text-center">
            <div className="text-xs text-slate-400 uppercase tracking-wider">Verification Status</div>
            <div className={`text-base font-bold mt-1 ${isVerified ? 'text-emerald-400' : 'text-rose-400'}`}>
              {isVerified ? 'VERIFIED' : 'FAILED'}
            </div>
          </div>

          <div className="bg-slate-950/80 p-3 rounded-xl border border-slate-800 text-center">
            <div className="text-xs text-slate-400 uppercase tracking-wider">Confidence Score</div>
            <div className="text-base font-bold text-indigo-300 mt-1">
              {(confidence * 100).toFixed(0)}%
            </div>
          </div>

          <div className="bg-slate-950/80 p-3 rounded-xl border border-slate-800 text-center">
            <div className="text-xs text-slate-400 uppercase tracking-wider">Pipeline Latency</div>
            <div className="text-base font-bold text-cyan-300 font-mono mt-1">
              {verificationReport.total_latency_ms} ms
            </div>
          </div>
        </div>
      )}

      {/* Individual Check Details */}
      {verificationReport?.check_details && (
        <div className="space-y-3">
          <label className="block text-xs font-medium text-slate-400 uppercase tracking-wider">
            Automated Check Results
          </label>
          <div className="space-y-3">
            {Object.entries(verificationReport.check_details).map(([key, detail]) => (
              <div
                key={key}
                className={`p-3.5 rounded-xl border space-y-2 font-mono text-xs ${
                  detail.passed
                    ? 'bg-slate-950/80 border-slate-800 text-slate-200'
                    : 'bg-rose-950/30 border-rose-800/80 text-rose-200'
                }`}
              >
                <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-white">{detail.check_name}</span>
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] ${
                        detail.passed
                          ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                          : 'bg-rose-950 text-rose-300 border border-rose-800'
                      }`}
                    >
                      {detail.passed ? 'PASSED' : 'FAILED'}
                    </span>
                  </div>
                  <span className="text-slate-400">⚡ {detail.latency_ms} ms</span>
                </div>

                <pre className="overflow-x-auto p-2 bg-slate-900/90 rounded-lg text-[11px] text-slate-300 max-h-32">
                  {detail.output}
                </pre>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
