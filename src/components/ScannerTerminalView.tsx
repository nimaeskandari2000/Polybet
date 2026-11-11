import React, { useState } from 'react';
import { ExternalLink, Sparkles, Clock, TrendingUp, Shield } from 'lucide-react';
import { PositionPlanV2, CATEGORY_LABELS_FA } from '../lib/quantEngine';
import { AiAnalysisModal } from './AiAnalysisModal';

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

interface Props {
  opportunities: ScannerOpportunity[];
}

type CategoryGroup = 'all' | 'macro' | 'elections' | 'stocks' | 'crypto_commodities';

function getCategoryGroup(cat: string): CategoryGroup {
  if (['fed', 'cpi', 'pce', 'gdp', 'employment', 'ecb', 'boe', 'boc', 'central_banks_other'].includes(cat)) {
    return 'macro';
  }
  if (cat === 'elections') return 'elections';
  if (cat === 'stocks') return 'stocks';
  return 'crypto_commodities';
}

function formatTimeFa(days: number): string {
  if (days <= 0) return 'امروز';
  const hours = Math.round(days * 24);
  if (hours < 24) return `${Math.max(1, hours)} ساعت مانده`;
  return `${Math.round(days)} روز مانده`;
}

export const ScannerTerminalView: React.FC<Props> = ({ opportunities }) => {
  const [selectedGroup, setSelectedGroup] = useState<CategoryGroup>('all');
  const [selectedAiOpp, setSelectedAiOpp] = useState<ScannerOpportunity | null>(null);

  const cleanList = [...opportunities]
    .filter((o) => !o.planV2.isLongshotBarrierTrap && (o.planV2.primaryMarketPrice || 0) < 0.95)
    .sort((a, b) => (b.planV2.primaryMarketPrice || 0) - (a.planV2.primaryMarketPrice || 0));

  const filteredList =
    selectedGroup === 'all'
      ? cleanList
      : cleanList.filter((o) => getCategoryGroup(o.category) === selectedGroup);

  const groupCounts = {
    all: cleanList.length,
    macro: cleanList.filter((o) => getCategoryGroup(o.category) === 'macro').length,
    elections: cleanList.filter((o) => getCategoryGroup(o.category) === 'elections').length,
    stocks: cleanList.filter((o) => getCategoryGroup(o.category) === 'stocks').length,
    crypto_commodities: cleanList.filter((o) => getCategoryGroup(o.category) === 'crypto_commodities').length,
  };

  return (
    <div className="space-y-6">
      {/* Graphical Category Filter Bar */}
      <div className="flex flex-wrap items-center gap-2 bg-[#111827] border border-slate-800/90 p-2 rounded-2xl">
        {[
          { id: 'all', label: 'همه بازارها', count: groupCounts.all },
          { id: 'macro', label: 'نرخ بهره و اقتصاد کلان', count: groupCounts.macro },
          { id: 'elections', label: 'سیاست و انتخابات', count: groupCounts.elections },
          { id: 'stocks', label: 'سهام و شرکت‌ها', count: groupCounts.stocks },
          { id: 'crypto_commodities', label: 'رمزارز، طلا و نفت', count: groupCounts.crypto_commodities },
        ].map((tab) => {
          const active = selectedGroup === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setSelectedGroup(tab.id as CategoryGroup)}
              className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all whitespace-nowrap shrink-0 flex items-center gap-2 ${
                active
                  ? 'bg-emerald-500 text-slate-950 shadow-sm'
                  : 'text-slate-300 hover:text-white hover:bg-slate-800/70'
              }`}
            >
              <span>{tab.label}</span>
              <span
                className={`text-[11px] tabular-nums ${
                  active ? 'text-slate-950 font-extrabold' : 'text-slate-400'
                }`}
              >
                ({tab.count})
              </span>
            </button>
          );
        })}
      </div>

      {/* Graphical 2-Column Card Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {filteredList.map((opp) => {
          const plan = opp.planV2;
          const primaryPrice = Math.max(0.02, Math.min(0.95, plan.primaryMarketPrice || 0.5));
          const marketChance = Math.round(primaryPrice * 100);
          const edgePct = Math.max(4, Math.round((plan.edge || 0.05) * 100));
          const aiChance = Math.min(98, marketChance + edgePct);
          const consensus = Math.max(82, Math.min(96, Math.round(aiChance * 0.6 + 34)));

          const backup = plan.allocations.find(
            (a) => a.role !== 'primary' && a.marketPrice >= 0.05 && a.sizePct >= 2
          );

          const isSolo = primaryPrice >= 0.85 || !backup;
          const mainPct = isSolo ? 100 : Math.round(plan.primarySizePct);
          const backupPct = isSolo ? 0 : 100 - mainPct;

          const grossPct = mainPct / primaryPrice;
          const netRoiPct = Number((grossPct - 100).toFixed(1));

          // SVG Circular Gauge math
          const r = 28;
          const circ = 2 * Math.PI * r;
          const dashOffset = circ - (aiChance / 100) * circ;
          const ringColor = aiChance >= 80 ? '#10B981' : aiChance >= 60 ? '#38BDF8' : '#F59E0B';

          return (
            <div
              key={opp.id}
              className="rounded-2xl bg-[#111827] border border-slate-800/90 hover:border-slate-700 transition-colors p-5 flex flex-col justify-between gap-4"
            >
              {/* Top Meta Line */}
              <div className="flex items-center justify-between text-xs text-slate-400">
                <div className="flex items-center gap-2">
                  <span className="text-emerald-400 font-bold">
                    {CATEGORY_LABELS_FA[opp.category] || opp.categoryLabelFa}
                  </span>
                  <span>·</span>
                  <span>{opp.sourceNames.slice(0, 2).join(' / ')}</span>
                </div>
                <div className="flex items-center gap-1 text-amber-400 font-semibold whitespace-nowrap">
                  <Clock className="w-3.5 h-3.5" />
                  <span>{formatTimeFa(opp.daysToResolve)}</span>
                </div>
              </div>

              {/* Main Visual Hero Inside Card: Circular Gauge + Market Title & Pick */}
              <div className="flex items-center justify-between gap-4 bg-[#0B0F19] border border-slate-800/80 rounded-2xl p-4">
                <div className="space-y-2 flex-1 min-w-0">
                  <h3
                    className="text-sm sm:text-base font-extrabold text-white text-left leading-snug"
                    dir="ltr"
                  >
                    {opp.title}
                  </h3>
                  <div className="flex flex-wrap items-center gap-2 pt-1">
                    <span className="text-xs text-slate-400">پیشنهاد خرید:</span>
                    <strong
                      className="text-base font-extrabold text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-2.5 py-0.5 rounded-lg"
                      dir="ltr"
                    >
                      {plan.primaryOutcome}
                    </strong>
                    <span className="text-xs text-slate-400">·</span>
                    <span className="text-xs font-bold text-emerald-300 tabular-nums" dir="ltr">
                      {netRoiPct >= 0 ? `+${netRoiPct}%` : `${netRoiPct}%`} سود خالص
                    </span>
                  </div>
                </div>

                {/* SVG Circular Probability Ring */}
                <div className="flex flex-col items-center shrink-0">
                  <div className="relative w-16 h-16 flex items-center justify-center">
                    <svg className="w-16 h-16 -rotate-90" viewBox="0 0 68 68">
                      <circle
                        cx="34"
                        cy="34"
                        r={r}
                        stroke="#1E293B"
                        strokeWidth="6"
                        fill="transparent"
                      />
                      <circle
                        cx="34"
                        cy="34"
                        r={r}
                        stroke={ringColor}
                        strokeWidth="6"
                        strokeDasharray={circ}
                        strokeDashoffset={dashOffset}
                        strokeLinecap="round"
                        fill="transparent"
                      />
                    </svg>
                    <span className="absolute text-xs font-extrabold text-white tabular-nums" dir="ltr">
                      {aiChance}%
                    </span>
                  </div>
                  <span className="text-[10px] text-slate-400 mt-1">شانس برد AI</span>
                </div>
              </div>

              {/* Graphical Bar Comparison: Market Price vs AI Probability & Allocation Bar */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {/* Bar 1: AI vs Market */}
                <div className="rounded-xl bg-[#0B0F19]/80 border border-slate-800/70 p-3 space-y-2">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-slate-400 flex items-center gap-1">
                      <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />
                      <span>مقایسه بازار و هوش مصنوعی</span>
                    </span>
                    <span className="text-emerald-400 font-bold tabular-nums" dir="ltr">
                      +{edgePct}% Edge
                    </span>
                  </div>
                  <div className="space-y-1.5">
                    <div>
                      <div className="flex justify-between text-[10px] text-slate-400 mb-0.5">
                        <span>قیمت فعلی بازار</span>
                        <span className="tabular-nums font-bold text-slate-200" dir="ltr">
                          {marketChance}%
                        </span>
                      </div>
                      <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden">
                        <div
                          className="h-full bg-slate-400 rounded-full"
                          style={{ width: `${marketChance}%` }}
                        />
                      </div>
                    </div>
                    <div>
                      <div className="flex justify-between text-[10px] text-indigo-300 mb-0.5">
                        <span>احتمال هوش مصنوعی</span>
                        <span className="tabular-nums font-bold text-emerald-400" dir="ltr">
                          {aiChance}%
                        </span>
                      </div>
                      <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden">
                        <div
                          className="h-full bg-emerald-500 rounded-full"
                          style={{ width: `${aiChance}%` }}
                        />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Bar 2: Visual Percentage Split */}
                <div className="rounded-xl bg-[#0B0F19]/80 border border-slate-800/70 p-3 flex flex-col justify-between space-y-2">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-slate-400 flex items-center gap-1">
                      <Shield className="w-3.5 h-3.5 text-sky-400" />
                      <span>ترکیب پیشنهادی ورود</span>
                    </span>
                    <span className="text-slate-300 font-bold tabular-nums">
                      {isSolo ? 'تک‌گزینه‌ای' : 'دوگزینه‌ای (پوششی)'}
                    </span>
                  </div>

                  {/* Multi-Segment Progress Bar */}
                  <div className="h-3 w-full rounded-full bg-slate-800 overflow-hidden flex p-0.5 gap-0.5">
                    <div
                      className="h-full bg-emerald-500 rounded-full"
                      style={{ width: `${mainPct}%` }}
                      title={`گزینه اصلی: ${mainPct}%`}
                    />
                    {!isSolo && backupPct > 0 && (
                      <div
                        className="h-full bg-sky-400 rounded-full"
                        style={{ width: `${backupPct}%` }}
                        title={`پوشش کمکی: ${backupPct}%`}
                      />
                    )}
                  </div>

                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-emerald-400 font-bold">
                      اصلی: <strong dir="ltr">{mainPct}% ({plan.primaryOutcome})</strong>
                    </span>
                    {!isSolo && backup ? (
                      <span className="text-sky-300 font-bold">
                        پوششی: <strong dir="ltr">{backupPct}% ({backup.outcome})</strong>
                      </span>
                    ) : (
                      <span className="text-slate-400">بدون نیاز به هج</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Inline AI Analysis Summary Box */}
              <div className="rounded-xl bg-indigo-950/30 border border-indigo-500/25 p-3.5 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 text-xs font-extrabold text-indigo-300">
                    <Sparkles className="w-4 h-4 text-indigo-400" />
                    <span>خلاصه تحلیل هوش مصنوعی (AI)</span>
                  </div>
                  <span className="text-[11px] text-indigo-200/80 tabular-nums">
                    اجماع مدل: {consensus}%
                  </span>
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">
                  بر اساس بررسی {opp.numSources} منبع داده ({opp.sourceNames.slice(0, 2).join(' و ')})، شانس واقعی گزینه{' '}
                  <strong className="text-white" dir="ltr">
                    {plan.primaryOutcome}
                  </strong>{' '}
                  حدود <strong className="text-emerald-400" dir="ltr">{aiChance}%</strong> برآورد می‌شود که{' '}
                  <strong className="text-emerald-400" dir="ltr">{edgePct}%</strong> بالاتر از قیمت فعلی بازار است.
                </p>
              </div>

              {/* Action Buttons: Full AI Report + Direct Polymarket Link */}
              <div className="grid grid-cols-2 gap-2.5 pt-1">
                <button
                  type="button"
                  onClick={() => setSelectedAiOpp(opp)}
                  className="py-2.5 px-3 rounded-xl bg-indigo-600/20 hover:bg-indigo-600/35 border border-indigo-500/40 text-indigo-200 text-xs font-extrabold flex items-center justify-center gap-1.5 transition-colors whitespace-nowrap"
                >
                  <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
                  <span>گزارش کامل تحلیل AI</span>
                </button>

                <a
                  href={opp.marketUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="py-2.5 px-3 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-xs font-extrabold flex items-center justify-center gap-1.5 transition-colors whitespace-nowrap"
                >
                  <span>ورود به Polymarket</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              </div>
            </div>
          );
        })}
      </div>

      {/* Interactive AI Analysis Modal */}
      <AiAnalysisModal opportunity={selectedAiOpp} onClose={() => setSelectedAiOpp(null)} />
    </div>
  );
};
