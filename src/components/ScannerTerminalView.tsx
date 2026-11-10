import React, { useState, useMemo } from 'react';
import {
  Search,
  Sparkles,
  ExternalLink,
  ShieldCheck,
  X,
  CheckCircle2,
  Calculator,
  ChevronDown,
  Clock,
  DollarSign,
  TrendingUp,
} from 'lucide-react';
import { PositionPlanV2, CATEGORY_LABELS_FA } from '../lib/quantEngine';

export interface ScannerOpportunity {
  id: string;
  groupKey: string;
  title: string;
  category: string;
  categoryLabelFa: string;
  categoryWasFixed: boolean;
  daysToResolve: number;
  marketUrl: string;
  numSources: number;
  legacyConsensusScore: number;
  calibratedConsensusScore: number;
  legacyPrimaryOutcome: string;
  legacyPrimarySizePct: number;
  legacyPrimaryPrice: number;
  planV2: PositionPlanV2;
  sourceNames: string[];
  loggedAtUtc: string;
}

interface AiAnalysisResult {
  verdictFa: string;
  fundamentalDriversFa: string[];
  hedgeCritiqueFa: string;
  tailRisksFa: string[];
  recommendedActionFa: string;
}

interface Props {
  opportunities: ScannerOpportunity[];
  bankroll: number;
  onBankrollChange: (val: number) => void;
  onLoadInSimulator: (opp: ScannerOpportunity) => void;
}

function formatTimeLeftFa(days: number): string {
  if (days <= 0) return 'در حال بسته شدن';
  const hours = Math.round(days * 24);
  if (hours < 24) return `${Math.max(1, hours)} ساعت مانده`;
  const wholeDays = Math.floor(days);
  const remHours = Math.round((days - wholeDays) * 24);
  if (remHours > 0 && wholeDays < 3) {
    return `${wholeDays} روز و ${remHours} ساعت مانده`;
  }
  return `${days.toFixed(1)} روز مانده`;
}

export const ScannerTerminalView: React.FC<Props> = ({
  opportunities,
  bankroll,
  onBankrollChange,
  onLoadInSimulator,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSection, setSelectedSection] = useState<'all' | 'economy' | 'markets' | 'politics'>('all');
  const [sortBy, setSortBy] = useState<'prob' | 'days' | 'roi'>('prob');

  const [aiModalOpp, setAiModalOpp] = useState<ScannerOpportunity | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiResult, setAiResult] = useState<{ source: string; analysis: AiAnalysisResult } | null>(null);

  const getSectionForCategory = (cat: string): 'economy' | 'markets' | 'politics' => {
    if (['fed', 'cpi', 'pce', 'gdp', 'employment', 'ecb', 'boe', 'boc', 'central_banks_other'].includes(cat)) {
      return 'economy';
    }
    if (['stocks', 'commodities', 'crypto'].includes(cat)) {
      return 'markets';
    }
    return 'politics';
  };

  const filteredOpportunities = useMemo(() => {
    return opportunities
      .filter((o) => {
        if (o.planV2.isLongshotBarrierTrap) return false;
        if (selectedSection !== 'all' && getSectionForCategory(o.category) !== selectedSection) {
          return false;
        }
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase();
          return (
            o.title.toLowerCase().includes(q) ||
            o.planV2.primaryOutcome.toLowerCase().includes(q) ||
            o.categoryLabelFa.includes(q)
          );
        }
        return true;
      })
      .sort((a, b) => {
        if (sortBy === 'days') {
          return a.daysToResolve - b.daysToResolve;
        }
        if (sortBy === 'roi') {
          const roiA = a.planV2.allocations[0]?.netRoiIfWinsPct ?? 0;
          const roiB = b.planV2.allocations[0]?.netRoiIfWinsPct ?? 0;
          return roiB - roiA;
        }
        return b.planV2.primaryMarketPrice - a.planV2.primaryMarketPrice;
      });
  }, [opportunities, selectedSection, searchQuery, sortBy]);

  const highProbCount = useMemo(
    () => filteredOpportunities.filter((o) => o.planV2.primaryMarketPrice >= 0.8).length,
    [filteredOpportunities]
  );

  const triggerAiAnalysis = async (opp: ScannerOpportunity) => {
    setAiModalOpp(opp);
    setAiLoading(true);
    setAiResult(null);
    try {
      const resp = await fetch('/api/ai-analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: opp.title,
          category: opp.categoryLabelFa,
          allocations: opp.planV2.allocations,
          edge: opp.planV2.edge,
          calibratedConsensus: opp.planV2.calibratedConsensusScore,
          warning: opp.planV2.warning,
        }),
      });
      const data = await resp.json();
      setAiResult(data);
    } catch {
      setAiResult({
        source: 'fallback',
        analysis: {
          verdictFa: 'خطا در برقراری ارتباط با سرور تحلیل هوش مصنوعی.',
          fundamentalDriversFa: [],
          hedgeCritiqueFa: '',
          tailRisksFa: [],
          recommendedActionFa: 'لطفاً دوباره تلاش کنید.',
        },
      });
    } finally {
      setAiLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Simple 3-Step Visual Guide Banner */}
      <div className="rounded-2xl border border-emerald-500/30 bg-gradient-to-br from-emerald-500/10 via-slate-900/90 to-sky-500/10 p-5 shadow-lg">
        <div className="text-sm font-extrabold text-emerald-400 mb-3 flex items-center gap-2">
          <span>💡 راهنمای سریع استفاده (در ۳ قدم ساده):</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="rounded-xl bg-slate-950/75 border border-slate-800 p-3.5 text-xs text-slate-300 leading-relaxed">
            <strong className="text-white block text-sm mb-1">۱. تعیین مبلغ سرمایه</strong>
            در کادر سبز زیر بنویسید برای هر بازار چند دلار در نظر گرفته‌اید (مثلاً ۱۰۰ یا ۱۰۰۰ دلار).
          </div>
          <div className="rounded-xl bg-slate-950/75 border border-slate-800 p-3.5 text-xs text-slate-300 leading-relaxed">
            <strong className="text-white block text-sm mb-1">۲. مشاهده پیشنهاد خرید</strong>
            در هر کارت، <span className="text-emerald-400 font-bold">«گام ۱ (کادر سبز)»</span> دقیقاً نشان می‌دهد کدام گزینه را بخرید و چقدر سود خالص می‌کنید.
          </div>
          <div className="rounded-xl bg-slate-950/75 border border-slate-800 p-3.5 text-xs text-slate-300 leading-relaxed">
            <strong className="text-white block text-sm mb-1">۳. ثبت در Polymarket</strong>
            روی دکمه آبی <span className="text-sky-400 font-bold">«ورود به بازار در Polymarket»</span> بالای هر کارت بزنید و همان گزینه را بخرید.
          </div>
        </div>
      </div>

      {/* Top Summary & Bankroll Calculator Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded-2xl border-2 border-emerald-500/40 bg-gradient-to-br from-emerald-500/15 to-slate-900/95 p-5 shadow-md">
          <label htmlFor="scanner-bankroll-input" className="block text-xs font-semibold text-emerald-300">
            💰 سرمایه شما برای هر بازار (دلار $)
          </label>
          <div className="mt-2 flex items-center gap-2.5">
            <div className="relative flex-1">
              <DollarSign className="w-4 h-4 text-emerald-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                id="scanner-bankroll-input"
                type="number"
                min={10}
                max={1000000}
                step={50}
                value={bankroll}
                onChange={(e) => onBankrollChange(Math.max(10, Number(e.target.value) || 1000))}
                dir="ltr"
                className="w-full rounded-xl bg-slate-950 border border-emerald-500/50 pl-8 pr-3 py-2 text-lg font-extrabold font-mono tabular-nums text-emerald-400 focus:border-emerald-400 focus:outline-none"
              />
            </div>
            <span className="text-xs font-bold text-emerald-300 shrink-0">دلار</span>
          </div>
          <div className="mt-2 text-[11px] text-slate-400">
            با تغییر این عدد، تمام مبالغ خرید و سودهای خالص پایین صفحه خودکار حساب می‌شوند
          </div>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-5 flex flex-col justify-center">
          <div className="text-xs text-slate-400 font-medium">📊 تعداد موقعیت‌های آماده معامله</div>
          <div className="mt-1.5 text-3xl font-extrabold font-mono tabular-nums text-white">
            {filteredOpportunities.length}
          </div>
          <div className="mt-1.5 text-xs text-slate-400">
            بازارهای بررسی‌شده و فیلترشده (بدون بازارهای ورزشی و کم‌عمق)
          </div>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-5 flex flex-col justify-center">
          <div className="text-xs text-slate-400 font-medium">✅ موقعیت‌های با شانس برد بالای ۸۰٪</div>
          <div className="mt-1.5 text-3xl font-extrabold font-mono tabular-nums text-emerald-400">
            {highProbCount}
          </div>
          <div className="mt-1.5 text-xs text-slate-400">
            گزینه‌هایی که احتمال برد بسیار بالایی در بازار دارند
          </div>
        </div>
      </div>

      {/* Category Pills & Search Bar */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-4 flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setSelectedSection('all')}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${
              selectedSection === 'all'
                ? 'bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/20'
                : 'bg-slate-950 text-slate-300 border border-slate-800 hover:border-slate-700'
            }`}
          >
            همه بازارها
          </button>
          <button
            type="button"
            onClick={() => setSelectedSection('economy')}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${
              selectedSection === 'economy'
                ? 'bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/20'
                : 'bg-slate-950 text-slate-300 border border-slate-800 hover:border-slate-700'
            }`}
          >
            📊 اقتصاد و تورم
          </button>
          <button
            type="button"
            onClick={() => setSelectedSection('markets')}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${
              selectedSection === 'markets'
                ? 'bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/20'
                : 'bg-slate-950 text-slate-300 border border-slate-800 hover:border-slate-700'
            }`}
          >
            📈 سهام و رمزارز
          </button>
          <button
            type="button"
            onClick={() => setSelectedSection('politics')}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${
              selectedSection === 'politics'
                ? 'bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/20'
                : 'bg-slate-950 text-slate-300 border border-slate-800 hover:border-slate-700'
            }`}
          >
            🗳️ سیاست و انتخابات
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-2.5 flex-1 lg:justify-end">
          <div className="relative flex-1 min-w-[220px] max-w-sm">
            <Search className="w-4 h-4 text-slate-400 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              placeholder="جستجوی نام بازار (مثلاً CPI، Bitcoin...)"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-xl bg-slate-950 border border-slate-800 pr-9 pl-3 py-2 text-xs text-white placeholder:text-slate-500 focus:border-emerald-500 focus:outline-none"
            />
          </div>

          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as 'prob' | 'days' | 'roi')}
            className="rounded-xl bg-slate-950 border border-slate-800 px-3 py-2 text-xs font-semibold text-slate-200 focus:border-emerald-500 focus:outline-none"
          >
            <option value="prob">مرتب‌سازی: بیشترین شانس برد</option>
            <option value="days">مرتب‌سازی: نزدیک‌ترین زمان نتیجه</option>
            <option value="roi">مرتب‌سازی: بیشترین درصد سود</option>
          </select>
        </div>
      </div>

      {/* Market Cards List */}
      <div className="space-y-5">
        {filteredOpportunities.map((opp) => {
          const plan = opp.planV2;
          const primaryPrice = Math.max(0.01, plan.primaryMarketPrice || 0.5);
          const winProbPct = Number((primaryPrice * 100).toFixed(1));

          // Filter backup legs to only realistic contenders (price >= 4c)
          const viableBackups = plan.allocations
            .filter((a) => a.role !== 'primary' && a.marketPrice >= 0.04 && a.sizePct >= 1.5)
            .slice(0, 2);

          // If primary is >= 88c or no viable backups exist, treat as 100% solo primary for clarity
          const isSoloPrimary = primaryPrice >= 0.88 || viableBackups.length === 0;
          const displayPrimaryPct = isSoloPrimary ? 100 : plan.primarySizePct;
          const displayPrimaryDollar = Math.round(bankroll * (displayPrimaryPct / 100));
          const displayPrimaryPayout = Math.round(displayPrimaryDollar / primaryPrice);
          const displayPrimaryNetProfit = displayPrimaryPayout - bankroll;
          const displayPrimaryRoiPct = Number(((displayPrimaryNetProfit / bankroll) * 100).toFixed(1));

          return (
            <article
              key={opp.id}
              className="rounded-2xl border border-slate-800/90 bg-slate-900/90 p-5 sm:p-6 shadow-xl hover:border-slate-700 transition-all"
            >
              {/* Card Header */}
              <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="px-3 py-1 rounded-full text-xs font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                    {CATEGORY_LABELS_FA[opp.category] || opp.categoryLabelFa}
                  </span>
                  <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold bg-amber-500/10 text-amber-300 border border-amber-500/30">
                    <Clock className="w-3.5 h-3.5" />
                    <span>{formatTimeLeftFa(opp.daysToResolve)}</span>
                  </span>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => triggerAiAnalysis(opp)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold transition-colors"
                  >
                    <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
                    <span>تحلیل هوشمند</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => onLoadInSimulator(opp)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold transition-colors"
                  >
                    <Calculator className="w-3.5 h-3.5 text-sky-400" />
                    <span>ماشین‌حساب دستی</span>
                  </button>
                  <a
                    href={opp.marketUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold shadow-md shadow-blue-600/25 transition-colors"
                  >
                    <span>ورود به بازار در Polymarket</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                </div>
              </div>

              {/* Market Title */}
              <h3 className="text-lg sm:text-xl font-extrabold text-white text-left mb-4" dir="ltr">
                {opp.title}
              </h3>

              {/* Visual Win Probability Bar */}
              <div className="rounded-xl bg-slate-950/80 border border-slate-800/80 p-3.5 mb-5">
                <div className="flex items-center justify-between text-xs text-slate-300 mb-2">
                  <span>شانس برد گزینه پیشنهادی (بر اساس قیمت فعلی بازار)</span>
                  <strong className="font-mono text-sm font-extrabold text-emerald-400" dir="ltr">
                    {winProbPct}%
                  </strong>
                </div>
                <div className="w-full h-2.5 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-emerald-500 to-teal-400 rounded-full"
                    style={{ width: `${Math.min(100, Math.max(5, winProbPct))}%` }}
                  />
                </div>
              </div>

              {/* Two-Box Clear Action Plan */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Box 1: Primary Recommendation */}
                <div className="rounded-2xl border border-emerald-500/40 bg-gradient-to-br from-emerald-500/12 to-slate-950/90 p-4 sm:p-5 flex flex-col justify-between">
                  <div>
                    <div className="flex flex-wrap items-center justify-between gap-2 mb-3.5">
                      <span className="px-3 py-1 rounded-full bg-emerald-500 text-slate-950 text-xs font-extrabold">
                        گام ۱ · پیشنهاد اصلی خرید
                      </span>
                      <span className="text-xs text-slate-400">
                        قیمت هر سهم:{' '}
                        <strong className="font-mono text-slate-200" dir="ltr">
                          {(primaryPrice * 100).toFixed(1)}¢
                        </strong>
                      </span>
                    </div>

                    <div className="rounded-xl bg-slate-950/90 border border-emerald-500/30 p-3.5 flex items-center justify-between gap-3 mb-4">
                      <span className="text-xs sm:text-sm font-bold text-slate-300">
                        این گزینه را بخرید:
                      </span>
                      <span
                        className="px-3 py-1 rounded-lg bg-emerald-500/15 text-emerald-300 font-mono text-base sm:text-lg font-extrabold"
                        dir="ltr"
                      >
                        {plan.primaryOutcome}
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-xl bg-slate-950/80 border border-slate-800 p-3">
                      <div className="text-[11px] text-slate-400">مبلغی که وارد می‌کنید</div>
                      <div className="mt-1 text-xl font-extrabold font-mono text-white" dir="ltr">
                        ${displayPrimaryDollar.toLocaleString()}
                      </div>
                      <div className="mt-0.5 text-[11px] text-slate-400">
                        ({displayPrimaryPct.toFixed(0)}٪ از کل سرمایه)
                      </div>
                    </div>

                    <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/30 p-3">
                      <div className="text-[11px] text-emerald-300">سود خالص شما در صورت برد</div>
                      <div className="mt-1 text-xl font-extrabold font-mono text-emerald-400" dir="ltr">
                        {displayPrimaryNetProfit >= 0 ? '+' : '-'}$
                        {Math.abs(displayPrimaryNetProfit).toLocaleString()}
                      </div>
                      <div className="mt-0.5 text-[11px] font-mono text-emerald-300" dir="ltr">
                        ({displayPrimaryRoiPct >= 0 ? '+' : ''}
                        {displayPrimaryRoiPct}% سود خالص)
                      </div>
                    </div>
                  </div>
                </div>

                {/* Box 2: Insurance / Backup Plan */}
                {isSoloPrimary ? (
                  <div className="rounded-2xl border border-dashed border-slate-700/80 bg-slate-950/60 p-5 flex flex-col justify-center">
                    <div className="flex items-center gap-2 mb-2">
                      <ShieldCheck className="w-5 h-5 text-emerald-400" />
                      <span className="text-sm font-extrabold text-emerald-400">
                        نیاز به خرید گزینه کمکی (بیمه) ندارد
                      </span>
                    </div>
                    <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
                      از آنجا که گزینه اصلی از نظر آماری شانس بالایی دارد، کل بودجه روی همان{' '}
                      <strong className="text-white" dir="ltr">
                        {plan.primaryOutcome}
                      </strong>{' '}
                      قرار می‌گیرد تا سود خالص شما کم نشود.
                    </p>
                  </div>
                ) : (
                  <div className="rounded-2xl border border-sky-500/35 bg-gradient-to-br from-sky-500/10 to-slate-950/90 p-4 sm:p-5 flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between gap-2 mb-2.5">
                        <span className="px-3 py-1 rounded-full bg-sky-400 text-slate-950 text-xs font-extrabold">
                          گام ۲ · بیمه ریسک (برای نسوختن کل پول)
                        </span>
                      </div>
                      <p className="text-xs text-slate-300 mb-3 leading-relaxed">
                        اگر گزینه اول نیاید و یکی از گزینه‌های محتمل زیر برنده شود، این خرید پوششی باعث می‌شود اصل پول شما حفظ شود:
                      </p>
                    </div>

                    <div className="space-y-2.5">
                      {viableBackups.map((b, idx) => {
                        const bDollar = Math.round(bankroll * (b.sizePct / 100));
                        const bPayout = b.marketPrice > 0 ? Math.round(bDollar / b.marketPrice) : 0;
                        return (
                          <div
                            key={b.outcome}
                            className="rounded-xl bg-slate-950/85 border border-sky-500/25 p-3 text-xs"
                          >
                            <div className="flex items-center justify-between mb-1.5">
                              <span className="text-slate-200 font-semibold">
                                گزینه جایگزین {idx + 1}:{' '}
                                <strong className="font-mono text-white" dir="ltr">
                                  {b.outcome}
                                </strong>
                              </span>
                              <span className="text-slate-400 font-mono" dir="ltr">
                                قیمت: {(b.marketPrice * 100).toFixed(1)}¢
                              </span>
                            </div>
                            <div className="flex flex-wrap items-center justify-between gap-2 text-slate-400">
                              <span>
                                مبلغ خرید:{' '}
                                <strong className="text-sky-400 font-mono text-sm" dir="ltr">
                                  ${bDollar.toLocaleString()}
                                </strong>{' '}
                                ({b.sizePct.toFixed(0)}٪ بودجه)
                              </span>
                              <span>
                                دریافتی در صورت برد:{' '}
                                <strong className="text-slate-200 font-mono" dir="ltr">
                                  ${bPayout.toLocaleString()}
                                </strong>
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>

              {/* Optional Collapsible Details Drawer */}
              <details className="mt-4 pt-3 border-t border-slate-800/80 group">
                <summary className="cursor-pointer list-none flex items-center justify-between text-xs font-semibold text-slate-400 hover:text-slate-200">
                  <span>📋 مشاهده جدول دقیق تعداد سهام (Shares) و جزئیات محاسبه</span>
                  <ChevronDown className="w-4 h-4 transition-transform group-open:rotate-180" />
                </summary>
                <div className="mt-3 overflow-x-auto rounded-xl border border-slate-800">
                  <table className="w-full text-right border-collapse text-xs">
                    <thead>
                      <tr className="bg-slate-950 text-slate-400 border-b border-slate-800">
                        <th className="py-2.5 px-3">نوع انتخاب</th>
                        <th className="py-2.5 px-3">گزینه</th>
                        <th className="py-2.5 px-3">قیمت هر سهم</th>
                        <th className="py-2.5 px-3">سهم از بودجه</th>
                        <th className="py-2.5 px-3">مبلغ دلاری</th>
                        <th className="py-2.5 px-3">تعداد سهام دریافتی</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 bg-slate-950/50">
                      {(isSoloPrimary
                        ? [
                            {
                              outcome: plan.primaryOutcome,
                              role: 'primary' as const,
                              marketPrice: primaryPrice,
                              sizePct: 100,
                            },
                          ]
                        : [plan.allocations[0], ...viableBackups].filter(Boolean)
                      ).map((leg) => {
                        const lDollar = Math.round(bankroll * (leg.sizePct / 100));
                        const lShares = leg.marketPrice > 0 ? lDollar / leg.marketPrice : 0;
                        return (
                          <tr key={leg.outcome}>
                            <td className="py-2.5 px-3">
                              <span
                                className={`inline-block px-2 py-0.5 rounded text-[11px] font-bold ${
                                  leg.role === 'primary'
                                    ? 'bg-emerald-500/15 text-emerald-300'
                                    : 'bg-sky-500/15 text-sky-300'
                                }`}
                              >
                                {leg.role === 'primary' ? 'گزینه اصلی خرید' : 'بیمه و پوشش ریسک'}
                              </span>
                            </td>
                            <td className="py-2.5 px-3 font-mono font-bold text-white" dir="ltr">
                              {leg.outcome}
                            </td>
                            <td className="py-2.5 px-3 font-mono text-slate-300" dir="ltr">
                              {(leg.marketPrice * 100).toFixed(1)}¢
                            </td>
                            <td className="py-2.5 px-3 font-mono text-slate-300" dir="ltr">
                              {leg.sizePct.toFixed(1)}%
                            </td>
                            <td className="py-2.5 px-3 font-mono font-bold text-emerald-400" dir="ltr">
                              ${lDollar.toLocaleString()}
                            </td>
                            <td className="py-2.5 px-3 font-mono text-slate-300" dir="ltr">
                              {lShares.toFixed(1)} سهم
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </details>
            </article>
          );
        })}
      </div>

      {/* AI Analysis Modal */}
      {aiModalOpp && (
        <div
          className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
        >
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-2xl w-full max-h-[85vh] overflow-y-auto shadow-2xl">
            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-emerald-400" />
                <h3 className="text-sm font-bold text-slate-100">تحلیل هوشمند بازار به زبان ساده</h3>
              </div>
              <button
                type="button"
                onClick={() => setAiModalOpp(null)}
                className="text-slate-400 hover:text-slate-200 p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-5 space-y-4">
              <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800">
                <div className="text-sm font-bold text-slate-100 text-left" dir="ltr">
                  {aiModalOpp.title}
                </div>
              </div>

              {aiLoading ? (
                <div className="py-12 text-center space-y-2">
                  <div className="inline-block w-6 h-6 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin" />
                  <p className="text-xs text-slate-400">در حال آماده‌سازی تحلیل بازار...</p>
                </div>
              ) : aiResult ? (
                <div className="space-y-4 text-xs leading-relaxed">
                  <div className="p-4 rounded-xl bg-emerald-950/30 border border-emerald-700/40">
                    <div className="font-bold text-emerald-300 mb-1 flex items-center gap-1.5">
                      <CheckCircle2 className="w-4 h-4" />
                      <span>جمع‌بندی نهایی:</span>
                    </div>
                    <p className="text-slate-200">{aiResult.analysis.verdictFa}</p>
                  </div>

                  {aiResult.analysis.fundamentalDriversFa?.length > 0 && (
                    <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                      <div className="font-bold text-slate-200 mb-2 flex items-center gap-1.5">
                        <TrendingUp className="w-4 h-4 text-sky-400" />
                        <span>نکات کلیدی این بازار:</span>
                      </div>
                      <ul className="list-disc list-inside space-y-1.5 text-slate-300">
                        {aiResult.analysis.fundamentalDriversFa.map((item, idx) => (
                          <li key={idx}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  <div className="p-4 rounded-xl bg-sky-950/30 border border-sky-700/40">
                    <div className="font-bold text-sky-300 mb-1">پیشنهاد عملیاتی:</div>
                    <p className="text-slate-200">{aiResult.analysis.recommendedActionFa}</p>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
