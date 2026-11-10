import React, { useEffect, useState } from 'react';
import {
  Activity,
  BarChart3,
  Bug,
  Calculator,
  Download,
  RefreshCw,
  Send,
  Terminal,
} from 'lucide-react';
import { ScannerTerminalView, ScannerOpportunity } from './components/ScannerTerminalView';
import { BacktestAnalyticsView } from './components/BacktestAnalyticsView';
import { AuditAndCodeView } from './components/AuditAndCodeView';
import { PositionSimulatorView } from './components/PositionSimulatorView';
import { AuditedTradeRow, CategoryAuditStat } from './lib/quantEngine';
import { BugReportItem, FixedPythonFile } from './lib/fixedPythonTemplates';

type ActiveTab = 'scanner' | 'backtest' | 'audit' | 'simulator';

interface DatasetPayload {
  auditResult: {
    trades: AuditedTradeRow[];
    summary: {
      totalMarkets: number;
      resolvedCount: number;
      pendingCount: number;
      legacyWinCount: number;
      legacyWinRatePct: number;
      legacyTotalReturnPct: number;
      legacyAvgReturnPct: number;
      repairedWinCount: number;
      repairedWinRatePct: number;
      repairedSecondarySaveCount: number;
      repairedTotalReturnPct: number;
      repairedAvgReturnPct: number;
      idealEngineTotalReturnPct: number;
      idealEngineAvgReturnPct: number;
      bug1BinaryFalseNegativesFixed: number;
      bug2MultiLegPnlCorrectedCount: number;
      bug3CategoryMisclassificationsFixed: number;
      bug6BarrierTrapAvoidedCount: number;
    };
    categoryBreakdown: CategoryAuditStat[];
  };
  opportunities: ScannerOpportunity[];
  bugs: BugReportItem[];
  fixedPythonFiles: FixedPythonFile[];
}

export default function App() {
  const [activeTab, setActiveTab] = useState<ActiveTab>('scanner');
  const [data, setData] = useState<DatasetPayload | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [scanningLive, setScanningLive] = useState<boolean>(false);
  const [sendingTelegram, setSendingTelegram] = useState<boolean>(false);
  const [scanStatusText, setScanStatusText] = useState<string>('');
  const [bankroll, setBankroll] = useState<number>(1000);
  const [simulatorTargetOpp, setSimulatorTargetOpp] = useState<ScannerOpportunity | null>(null);

  useEffect(() => {
    fetch('/api/dataset')
      .then((r) => r.json())
      .then((payload: DatasetPayload) => {
        setData(payload);
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
      });
  }, []);

  const handleLiveScan = async () => {
    setScanningLive(true);
    setScanStatusText('در حال دریافت داده‌های زنده از Gamma API...');
    try {
      const resp = await fetch('/api/live-scan');
      const result = await resp.json();
      if (result.opportunities && data) {
        setData({
          ...data,
          opportunities: result.opportunities,
        });
        setScanStatusText(
          result.source === 'polymarket_gamma_live'
            ? `بروزرسانی شد (${result.liveFetchedCount} بازار زنده جدید)`
            : 'کالیبراسیون مجدد از آخرین اسنپ‌شات انجام شد'
        );
      }
    } catch {
      setScanStatusText('اسنپ‌شات محلی کالیبره فعال است');
    } finally {
      setScanningLive(false);
      setTimeout(() => setScanStatusText(''), 4000);
    }
  };

  const handleSendTelegram = async () => {
    setSendingTelegram(true);
    setScanStatusText('در حال ارسال گزارش به تلگرام...');
    try {
      const resp = await fetch('/api/telegram/send', { method: 'POST' });
      const result = await resp.json();
      setScanStatusText(result.statusFa || 'پاسخ از سرور تلگرام دریافت شد');
    } catch {
      setScanStatusText('خطا در ارسال درخواست تلگرام');
    } finally {
      setSendingTelegram(false);
      setTimeout(() => setScanStatusText(''), 6000);
    }
  };

  const handleOpenInSimulator = (opp: ScannerOpportunity) => {
    setSimulatorTargetOpp(opp);
    setActiveTab('simulator');
  };

  return (
    <div className="min-h-screen bg-[#080D1A] text-slate-100 flex flex-col">
      <header className="sticky top-0 z-40 bg-[#080D1A]/90 backdrop-blur-md border-b border-slate-800/80">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex flex-wrap items-center justify-between gap-4">
          {/* Brand */}
          <div className="flex items-center gap-3 shrink-0">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center text-white shadow-lg shadow-emerald-500/20">
              <Terminal className="w-5 h-5" />
            </div>
            <div>
              <span className="font-extrabold text-sm sm:text-base text-white block">
                دستیار هوشمند معاملات Polymarket
              </span>
              <p className="text-[11px] text-slate-400 hidden sm:block">
                پیشنهاد شفاف خرید، محاسبه خودکار سود خالص و بیمه ریسک
              </p>
            </div>
          </div>

          {/* Friendly Navigation Tabs */}
          <nav aria-label="ناوبری اصلی" className="flex flex-wrap items-center gap-1.5">
            <button
              type="button"
              onClick={() => setActiveTab('scanner')}
              className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold transition-all whitespace-nowrap ${
                activeTab === 'scanner'
                  ? 'bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/25'
                  : 'bg-slate-900 text-slate-300 border border-slate-800 hover:border-slate-700'
              }`}
            >
              <Activity className="w-3.5 h-3.5" />
              <span>📡 پیشنهادهای امروز</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('backtest')}
              className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold transition-all whitespace-nowrap ${
                activeTab === 'backtest'
                  ? 'bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/25'
                  : 'bg-slate-900 text-slate-300 border border-slate-800 hover:border-slate-700'
              }`}
            >
              <BarChart3 className="w-3.5 h-3.5" />
              <span>🏆 کارنامه و نتایج قبلی</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('simulator')}
              className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold transition-all whitespace-nowrap ${
                activeTab === 'simulator'
                  ? 'bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/25'
                  : 'bg-slate-900 text-slate-300 border border-slate-800 hover:border-slate-700'
              }`}
            >
              <Calculator className="w-3.5 h-3.5" />
              <span>🧮 ماشین‌حساب دستی</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('audit')}
              className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold transition-all whitespace-nowrap ${
                activeTab === 'audit'
                  ? 'bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/25'
                  : 'bg-slate-900 text-slate-300 border border-slate-800 hover:border-slate-700'
              }`}
            >
              <Bug className="w-3.5 h-3.5" />
              <span>📦 کدها و ریپوی گیت‌هاب</span>
            </button>
          </nav>

          {/* Action CTAs */}
          <div className="flex items-center gap-2 shrink-0">
            <a
              href="/api/download-github-repo"
              download="polybet-quant-v2-github-repo.zip"
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition-colors whitespace-nowrap shrink-0 shadow-md shadow-emerald-600/20"
            >
              <Download className="w-3.5 h-3.5" />
              <span>دانلود ریپوی گیت‌هاب (.ZIP)</span>
            </a>
            <button
              type="button"
              onClick={handleSendTelegram}
              disabled={sendingTelegram}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-sky-500/15 hover:bg-sky-500/25 border border-sky-500/35 disabled:opacity-60 text-sky-300 text-xs font-bold transition-colors whitespace-nowrap shrink-0"
            >
              <Send className="w-3.5 h-3.5" />
              <span>ارسال تلگرام</span>
            </button>
            <button
              type="button"
              onClick={handleLiveScan}
              disabled={scanningLive}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 disabled:opacity-60 text-slate-200 text-xs font-bold transition-colors whitespace-nowrap shrink-0"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${scanningLive ? 'animate-spin' : ''}`} />
              <span className="hidden md:inline">بروزرسانی زنده</span>
            </button>
          </div>
        </div>
        {scanStatusText && (
          <div className="bg-slate-900/95 border-t border-slate-800 px-4 py-1.5 text-center text-xs text-emerald-400">
            {scanStatusText}
          </div>
        )}
      </header>

      {/* Main Content Viewport */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6">
        {loading || !data ? (
          <div className="space-y-4">
            <div className="h-24 bg-[#0F1623] border border-slate-800 animate-pulse" />
            <div className="h-96 bg-[#0F1623] border border-slate-800 animate-pulse" />
          </div>
        ) : (
          <>
            {activeTab === 'scanner' && (
              <ScannerTerminalView
                opportunities={data.opportunities}
                bankroll={bankroll}
                onBankrollChange={setBankroll}
                onLoadInSimulator={handleOpenInSimulator}
              />
            )}

            {activeTab === 'backtest' && (
              <BacktestAnalyticsView
                trades={data.auditResult.trades}
                summary={data.auditResult.summary}
                categoryBreakdown={data.auditResult.categoryBreakdown}
              />
            )}

            {activeTab === 'audit' && (
              <AuditAndCodeView
                bugs={data.bugs}
                fixedFiles={data.fixedPythonFiles}
              />
            )}

            {activeTab === 'simulator' && (
              <PositionSimulatorView
                initialOpportunity={simulatorTargetOpp}
                defaultBankroll={bankroll}
              />
            )}
          </>
        )}
      </main>
    </div>
  );
}
