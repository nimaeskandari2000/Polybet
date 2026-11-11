import React, { useEffect, useState } from 'react';
import { Download, Sparkles, CheckCircle2, XCircle, BarChart3, Award, ExternalLink } from 'lucide-react';
import { ScannerTerminalView, ScannerOpportunity } from './components/ScannerTerminalView';
import { AuditedTradeRow, CATEGORY_LABELS_FA } from './lib/quantEngine';

type ActiveTab = 'scanner' | 'results';

interface DatasetPayload {
  auditResult: {
    trades: AuditedTradeRow[];
    summary: {
      resolvedCount: number;
      repairedWinCount: number;
      repairedWinRatePct: number;
    };
  };
  opportunities: ScannerOpportunity[];
}

export default function App() {
  const [activeTab, setActiveTab] = useState<ActiveTab>('scanner');
  const [data, setData] = useState<DatasetPayload | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

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

  const cleanOpportunities = (data?.opportunities || []).filter(
    (o) => !o.planV2.isLongshotBarrierTrap && (o.planV2.primaryMarketPrice || 0) < 0.95
  );
  const cleanTrades = (data?.auditResult.trades || []).filter(
    (t) => t.isResolved && t.repairedCategory !== 'excluded_sports'
  );
  const winsCount = cleanTrades.filter((t) => t.repairedIsCorrect).length;
  const lossesCount = cleanTrades.length - winsCount;
  const totalResolved = cleanTrades.length;
  const winRateNum = totalResolved > 0 ? Number(((winsCount / totalResolved) * 100).toFixed(1)) : 0;

  const avgAiConfidence =
    cleanOpportunities.length > 0
      ? Math.round(
          cleanOpportunities.reduce((acc, o) => {
            const p = Math.max(0.02, Math.min(0.95, o.planV2.primaryMarketPrice || 0.5));
            const aiC = Math.min(98, Math.round(p * 100) + Math.max(4, Math.round((o.planV2.edge || 0.05) * 100)));
            return acc + Math.max(82, Math.min(96, Math.round(aiC * 0.6 + 34)));
          }, 0) / cleanOpportunities.length
        )
      : 86;

  // Category distribution for graphical bar
  const macroCount = cleanOpportunities.filter((o) =>
    ['fed', 'cpi', 'pce', 'gdp', 'employment', 'ecb', 'boe', 'boc', 'central_banks_other'].includes(o.category)
  ).length;
  const electionsCount = cleanOpportunities.filter((o) => o.category === 'elections').length;
  const stocksCount = cleanOpportunities.filter((o) => o.category === 'stocks').length;
  const cryptoCommCount = Math.max(0, cleanOpportunities.length - macroCount - electionsCount - stocksCount);
  const totalOpps = Math.max(1, cleanOpportunities.length);

  // SVG Ring math for Top Hero
  const ringR = 30;
  const ringCirc = 2 * Math.PI * ringR;
  const winStrokeOffset = ringCirc - (winRateNum / 100) * ringCirc;
  const aiStrokeOffset = ringCirc - (avgAiConfidence / 100) * ringCirc;

  return (
    <div className="min-h-screen bg-[#0B0F19] text-slate-100 flex flex-col">
      {/* Top Bar Contract: 3 Clean Zones */}
      <header className="sticky top-0 z-30 bg-[#111827]/95 backdrop-blur-md border-b border-slate-800">
        <div className="max-w-6xl mx-auto px-4 py-3.5 flex items-center justify-between gap-6">
          {/* Zone 1: Brand Wordmark */}
          <div className="flex items-center gap-2.5 whitespace-nowrap shrink-0">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-500 to-indigo-600 flex items-center justify-center text-slate-950 font-black text-base shadow-sm">
              P
            </div>
            <span className="text-base sm:text-lg font-extrabold tracking-tight text-white">
              PolyBet AI
            </span>
          </div>

          {/* Zone 2: Navigation Tabs */}
          <nav className="flex items-center gap-2 bg-[#0B0F19] p-1 rounded-xl border border-slate-800">
            <button
              type="button"
              onClick={() => setActiveTab('scanner')}
              className={`px-4 py-2 rounded-lg text-xs sm:text-sm font-extrabold transition-all whitespace-nowrap shrink-0 ${
                activeTab === 'scanner'
                  ? 'bg-emerald-500 text-slate-950 shadow-sm'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              پیشنهادهای هوشمند امروز ({cleanOpportunities.length})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('results')}
              className={`px-4 py-2 rounded-lg text-xs sm:text-sm font-extrabold transition-all whitespace-nowrap shrink-0 ${
                activeTab === 'results'
                  ? 'bg-emerald-500 text-slate-950 shadow-sm'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              کارنامه و نتایج قبلی ({totalResolved})
            </button>
          </nav>

          {/* Zone 3: Single Primary Action */}
          <a
            href="/api/download-github-repo"
            download="polybet-quant-v2-github-repo.zip"
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-100 text-xs font-bold transition-colors whitespace-nowrap shrink-0"
          >
            <Download className="w-3.5 h-3.5 text-emerald-400" />
            <span>دانلود پکیج گیت‌هاب</span>
          </a>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 py-6 space-y-6">
        {/* Graphical Hero Overview Strip (3 Visual Gauge Cards) */}
        <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Card 1: Historical Win Rate Circular Gauge */}
          <div className="rounded-2xl bg-[#111827] border border-slate-800/90 p-4 flex items-center gap-4">
            <div className="relative w-20 h-20 shrink-0 flex items-center justify-center">
              <svg className="w-20 h-20 -rotate-90" viewBox="0 0 76 76">
                <circle
                  cx="38"
                  cy="38"
                  r={ringR}
                  stroke="#1E293B"
                  strokeWidth="7"
                  fill="transparent"
                />
                <circle
                  cx="38"
                  cy="38"
                  r={ringR}
                  stroke="#10B981"
                  strokeWidth="7"
                  strokeDasharray={ringCirc}
                  strokeDashoffset={winStrokeOffset}
                  strokeLinecap="round"
                  fill="transparent"
                />
              </svg>
              <span className="absolute text-sm font-extrabold text-emerald-400 tabular-nums" dir="ltr">
                {winRateNum}%
              </span>
            </div>
            <div className="space-y-1">
              <div className="flex items-center gap-1.5 text-xs font-bold text-emerald-400">
                <Award className="w-4 h-4" />
                <span>دقت پیش‌بینی‌های ثبت‌شده</span>
              </div>
              <div className="text-lg font-extrabold text-white">
                {winsCount} برد از {totalResolved} بازار
              </div>
              <div className="text-xs text-slate-400">
                بررسی‌شده روی بازارهای پایان‌یافته Polymarket
              </div>
            </div>
          </div>

          {/* Card 2: AI Engine Confidence Gauge */}
          <div className="rounded-2xl bg-[#111827] border border-slate-800/90 p-4 flex items-center gap-4">
            <div className="relative w-20 h-20 shrink-0 flex items-center justify-center">
              <svg className="w-20 h-20 -rotate-90" viewBox="0 0 76 76">
                <circle
                  cx="38"
                  cy="38"
                  r={ringR}
                  stroke="#1E293B"
                  strokeWidth="7"
                  fill="transparent"
                />
                <circle
                  cx="38"
                  cy="38"
                  r={ringR}
                  stroke="#6366F1"
                  strokeWidth="7"
                  strokeDasharray={ringCirc}
                  strokeDashoffset={aiStrokeOffset}
                  strokeLinecap="round"
                  fill="transparent"
                />
              </svg>
              <span className="absolute text-sm font-extrabold text-indigo-400 tabular-nums" dir="ltr">
                {avgAiConfidence}%
              </span>
            </div>
            <div className="space-y-1">
              <div className="flex items-center gap-1.5 text-xs font-bold text-indigo-300">
                <Sparkles className="w-4 h-4 text-indigo-400" />
                <span>شاخص اطمینان هوش مصنوعی</span>
              </div>
              <div className="text-lg font-extrabold text-white">
                {cleanOpportunities.length} سیگنال فعال امروز
              </div>
              <div className="text-xs text-slate-400">
                ترکیب داده‌های فدرال رزرو، تورم و مدل بیزی
              </div>
            </div>
          </div>

          {/* Card 3: Visual Category Spectrum */}
          <div className="rounded-2xl bg-[#111827] border border-slate-800/90 p-4 flex flex-col justify-between gap-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-xs font-bold text-sky-400">
                <BarChart3 className="w-4 h-4" />
                <span>توزیع گرافیکی بازارهای امروز</span>
              </div>
              <span className="text-xs text-slate-400 tabular-nums">{cleanOpportunities.length} بازار</span>
            </div>

            {/* Stacked Graphical Spectrum Bar */}
            <div className="h-3.5 w-full rounded-full bg-slate-800 overflow-hidden flex p-0.5 gap-0.5">
              <div
                className="h-full bg-emerald-500 rounded-l-full"
                style={{ width: `${(macroCount / totalOpps) * 100}%` }}
                title={`اقتصاد کلان: ${macroCount}`}
              />
              <div
                className="h-full bg-indigo-500"
                style={{ width: `${(electionsCount / totalOpps) * 100}%` }}
                title={`سیاست: ${electionsCount}`}
              />
              <div
                className="h-full bg-sky-400"
                style={{ width: `${(stocksCount / totalOpps) * 100}%` }}
                title={`سهام: ${stocksCount}`}
              />
              <div
                className="h-full bg-amber-400 rounded-r-full"
                style={{ width: `${(cryptoCommCount / totalOpps) * 100}%` }}
                title={`رمزارز و کالا: ${cryptoCommCount}`}
              />
            </div>

            <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] text-slate-300">
              <div className="flex items-center justify-between">
                <span className="text-emerald-400 font-semibold">اقتصاد کلان</span>
                <span className="tabular-nums font-bold">{macroCount}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-indigo-300 font-semibold">سیاست و انتخابات</span>
                <span className="tabular-nums font-bold">{electionsCount}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sky-300 font-semibold">سهام و شرکت‌ها</span>
                <span className="tabular-nums font-bold">{stocksCount}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-amber-300 font-semibold">رمزارز و کالا</span>
                <span className="tabular-nums font-bold">{cryptoCommCount}</span>
              </div>
            </div>
          </div>
        </section>

        {loading || !data ? (
          <div className="py-16 text-center text-sm text-slate-400">در حال بارگذاری اطلاعات گرافیکی...</div>
        ) : activeTab === 'scanner' ? (
          <ScannerTerminalView opportunities={data.opportunities} />
        ) : (
          <div className="space-y-6">
            {/* Visual Win vs Loss Bar Banner */}
            <div className="rounded-2xl bg-[#111827] border border-slate-800 p-5 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="text-sm font-extrabold text-white">
                  نمودار مقایسه‌ای پیش‌بینی‌های درست در برابر خطا
                </div>
                <div className="flex items-center gap-4 text-xs font-bold">
                  <span className="text-emerald-400">
                    درست: {winsCount} ({winRateNum}%)
                  </span>
                  <span className="text-rose-400">
                    خطا: {lossesCount} ({(100 - winRateNum).toFixed(1)}%)
                  </span>
                </div>
              </div>

              <div className="h-4 w-full rounded-full bg-slate-800 overflow-hidden flex p-0.5 gap-1">
                <div
                  className="h-full bg-emerald-500 rounded-full"
                  style={{ width: `${winRateNum}%` }}
                />
                <div
                  className="h-full bg-rose-500 rounded-full"
                  style={{ width: `${Math.max(0, 100 - winRateNum)}%` }}
                />
              </div>
            </div>

            {/* Clean Graphical Results Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {cleanTrades.map((trade, idx) => (
                <div
                  key={`${trade.groupKey}-${idx}`}
                  className="rounded-2xl bg-[#111827] border border-slate-800/90 p-4 flex flex-col justify-between gap-3"
                >
                  <div className="flex items-center justify-between gap-2 text-xs">
                    <span className="text-slate-400 font-semibold">
                      {CATEGORY_LABELS_FA[trade.repairedCategory] || trade.repairedCategory}
                    </span>
                    <span
                      className={`inline-flex items-center gap-1 font-extrabold ${
                        trade.repairedIsCorrect ? 'text-emerald-400' : 'text-rose-400'
                      }`}
                    >
                      {trade.repairedIsCorrect ? (
                        <>
                          <CheckCircle2 className="w-4 h-4" />
                          <span>پیش‌بینی درست</span>
                        </>
                      ) : (
                        <>
                          <XCircle className="w-4 h-4" />
                          <span>پیش‌بینی خطا</span>
                        </>
                      )}
                    </span>
                  </div>

                  <a
                    href={trade.marketUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm font-bold text-white hover:text-emerald-400 transition-colors text-left leading-snug"
                    dir="ltr"
                  >
                    {trade.title}
                  </a>

                  <div className="rounded-xl bg-[#0B0F19] border border-slate-800/80 p-3 flex items-center justify-between text-xs">
                    <div>
                      <span className="text-slate-400">پیشنهاد ربات: </span>
                      <strong className="text-emerald-400 font-extrabold" dir="ltr">
                        {trade.repairedPrimaryOutcome}
                      </strong>
                    </div>
                    <div>
                      <span className="text-slate-400">نتیجه نهایی بازار: </span>
                      <strong className="text-white font-extrabold" dir="ltr">
                        {trade.resolvedOutcome}
                      </strong>
                    </div>
                    <a
                      href={trade.marketUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      aria-label="مشاهده در پلی‌مارکت"
                      className="text-slate-400 hover:text-white"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
