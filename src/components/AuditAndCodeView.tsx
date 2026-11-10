import React, { useState } from 'react';
import {
  Bug,
  FileCode2,
  Copy,
  Check,
  Download,
  AlertOctagon,
  Wrench,
  Database,
  FolderGit2,
  ExternalLink,
  Terminal,
} from 'lucide-react';
import { BugReportItem, FixedPythonFile } from '../lib/fixedPythonTemplates';

interface Props {
  bugs: BugReportItem[];
  fixedFiles: FixedPythonFile[];
}

export const AuditAndCodeView: React.FC<Props> = ({ bugs, fixedFiles }) => {
  const [subTab, setSubTab] = useState<'python_code' | 'bugs'>('python_code');
  const [selectedBugId, setSelectedBugId] = useState<string>(bugs[0]?.id || '');
  const [selectedFileIndex, setSelectedFileIndex] = useState<number>(0);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const activeBug = bugs.find((b) => b.id === selectedBugId) || bugs[0];
  const activeFile = fixedFiles[selectedFileIndex] || fixedFiles[0];

  const handleCopy = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const handleDownloadFile = (file: FixedPythonFile) => {
    const blob = new Blob([file.code], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = file.filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const gitPushCommands = `unzip polybet-quant-v2-github-repo.zip -d polybet-quant-v2
cd polybet-quant-v2
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main --force`;

  return (
    <div className="space-y-6">
      {/* Turnkey GitHub Repository Download & Push Box */}
      <div className="border border-emerald-700/50 bg-[#0F1623] p-5 space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-slate-800 pb-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-emerald-400 text-xs font-mono font-bold">
              <FolderGit2 className="w-4 h-4" />
              <span>STANDALONE INITIALIZED GITHUB REPOSITORY (.GIT + WORKFLOWS + SOURCES + DOCS)</span>
            </div>
            <h2 className="text-base sm:text-lg font-bold text-slate-100">
              پکیج کامل ریپازیتوری گیت‌هاب ربات پایتون (PolyBet Quant v2.0 — آماده Push مستقیم)
            </h2>
            <p className="text-xs text-slate-300 leading-relaxed">
              فایل فشرده زیر یک <strong>ریپازیتوری گیت‌هاب خالص و مقداردهی‌شده با Git (شاخه main)</strong> است که شامل پوشه{' '}
              <code className="text-emerald-300 font-mono" dir="ltr">.github/workflows/</code>، پکیج کامل ۱۵ ماژول{' '}
              <code className="text-emerald-300 font-mono" dir="ltr">sources/</code>، داشبورد ارتقایافته GitHub Pages در{' '}
              <code className="text-emerald-300 font-mono" dir="ltr">docs/index.html</code> و{' '}
              <code className="text-emerald-300 font-mono" dir="ltr">docs/results.html</code>، فایل‌های CSV اصلاح‌شده و تمام اسکریپت‌های پایتون است.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5 shrink-0">
            <a
              href="/api/download-github-repo"
              download="polybet-quant-v2-github-repo.zip"
              className="inline-flex items-center gap-2 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition-colors"
            >
              <Download className="w-4 h-4" />
              <span>دانلود کامل ریپوی گیت‌هاب (.ZIP)</span>
            </a>

            <a
              href="/github-pages/index.html"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-2.5 bg-slate-900 hover:bg-slate-800 text-slate-200 border border-slate-700 text-xs font-medium transition-colors"
            >
              <span>پیش‌نمایش docs/index.html</span>
              <ExternalLink className="w-3.5 h-3.5 text-emerald-400" />
            </a>

            <a
              href="/github-pages/results.html"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-2.5 bg-slate-900 hover:bg-slate-800 text-slate-200 border border-slate-700 text-xs font-medium transition-colors"
            >
              <span>پیش‌نمایش docs/results.html</span>
              <ExternalLink className="w-3.5 h-3.5 text-sky-400" />
            </a>
          </div>
        </div>

        {/* Git Push Instructions */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-center">
          <div className="lg:col-span-5 space-y-1.5 text-xs text-slate-300">
            <div className="font-bold text-slate-100 flex items-center gap-1.5">
              <Terminal className="w-3.5 h-3.5 text-emerald-400" />
              <span>نحوه انتقال ۳۰ ثانیه‌ای به گیت‌هاب شما:</span>
            </div>
            <p className="text-slate-400 leading-relaxed">
              پوشه <code className="font-mono text-slate-200" dir="ltr">.git</code> از قبل داخل فایل ZIP ساخته شده و کامیت اولیه روی شاخه <code className="font-mono text-slate-200" dir="ltr">main</code> ثبت شده است. کافی است فایل ZIP را استخراج کرده و آدرس ریپوی خودتان را ست کنید:
            </p>
          </div>
          <div className="lg:col-span-7 relative">
            <pre
              dir="ltr"
              className="p-3 bg-slate-950 border border-slate-800 text-[11px] font-mono text-emerald-300 overflow-x-auto leading-relaxed"
            >
              <code>{gitPushCommands}</code>
            </pre>
            <button
              type="button"
              onClick={() => handleCopy(gitPushCommands, 'git-push-cmd')}
              className="absolute top-2 right-2 inline-flex items-center gap-1 px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-[11px] text-slate-200 border border-slate-700"
            >
              {copiedKey === 'git-push-cmd' ? (
                <>
                  <Check className="w-3 h-3 text-emerald-400" />
                  <span>کپی شد</span>
                </>
              ) : (
                <>
                  <Copy className="w-3 h-3" />
                  <span>کپی دستورات Git</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Sub-navigation Header */}
      <div className="border border-slate-800 bg-[#0F1623] p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h3 className="text-sm font-bold text-slate-100">
            مرورگر درختی فایل‌های ریپازیتوری گیت‌هاب و کالبدشکافی ۱۱ باگ برطرف‌شده
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            مشاهده و بررسی تک‌تک فایل‌های داخل ریپازیتوری (شامل ورک‌فلوهای GitHub Actions، ماژول‌های پایتون و مستندات)
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={() => setSubTab('python_code')}
            className={`inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium transition-colors ${
              subTab === 'python_code'
                ? 'bg-emerald-600 text-white'
                : 'bg-slate-900 text-slate-300 border border-slate-800 hover:text-white'
            }`}
          >
            <FileCode2 className="w-3.5 h-3.5" />
            <span>فایل‌های ریپازیتوری گیت‌هاب ({fixedFiles.length} فایل)</span>
          </button>

          <button
            type="button"
            onClick={() => setSubTab('bugs')}
            className={`inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-medium transition-colors ${
              subTab === 'bugs'
                ? 'bg-emerald-600 text-white'
                : 'bg-slate-900 text-slate-300 border border-slate-800 hover:text-white'
            }`}
          >
            <Bug className="w-3.5 h-3.5" />
            <span>کالبدشکافی ۱۱ باگ بحرانی (شامل ورک‌فلوها)</span>
          </button>
        </div>
      </div>

      {subTab === 'bugs' ? (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left / Right Sidebar of 11 Bugs */}
          <div className="lg:col-span-4 border border-slate-800 bg-[#0F1623] divide-y divide-slate-800">
            {bugs.map((bug) => {
              const isSelected = bug.id === activeBug?.id;
              return (
                <button
                  key={bug.id}
                  type="button"
                  onClick={() => setSelectedBugId(bug.id)}
                  className={`w-full text-right p-3.5 transition-colors flex items-start gap-3 ${
                    isSelected ? 'bg-slate-800/80' : 'hover:bg-slate-900/60'
                  }`}
                >
                  <span
                    className={`font-mono tabular-nums text-xs font-bold px-2 py-0.5 border shrink-0 ${
                      bug.severity === 'CRITICAL'
                        ? 'text-rose-400 border-rose-800/60 bg-rose-950/30'
                        : 'text-amber-400 border-amber-800/60 bg-amber-950/30'
                    }`}
                  >
                    #{bug.number}
                  </span>
                  <div className="space-y-1 min-w-0">
                    <div className="text-xs font-bold text-slate-100 leading-snug">
                      {bug.titleFa}
                    </div>
                    <div className="text-[11px] font-mono text-slate-400 truncate" dir="ltr">
                      {bug.fileAffected}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Detailed Bug Forensic Panel */}
          {activeBug && (
            <div className="lg:col-span-8 border border-slate-800 bg-[#0F1623] p-6 space-y-5">
              <div className="border-b border-slate-800 pb-4 space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                  <span className="font-mono text-emerald-400" dir="ltr">
                    File: {activeBug.fileAffected}
                  </span>
                  <span
                    className={`font-mono font-bold ${
                      activeBug.severity === 'CRITICAL' ? 'text-rose-400' : 'text-amber-400'
                    }`}
                  >
                    شدت خطا: {activeBug.severity}
                  </span>
                </div>
                <h3 className="text-lg font-bold text-slate-100">{activeBug.titleFa}</h3>
                <div className="text-xs font-mono text-slate-400" dir="ltr">
                  {activeBug.titleEn}
                </div>
              </div>

              {/* Impact Banner */}
              <div className="p-3.5 bg-rose-950/20 border border-rose-800/40 flex items-start gap-3">
                <AlertOctagon className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                <div className="text-xs">
                  <span className="font-bold text-rose-300">تأثیر مستقیم روی عملکرد ربات: </span>
                  <span className="text-slate-200">{activeBug.impactMetric}</span>
                </div>
              </div>

              {/* Technical Explanation */}
              <div className="space-y-2">
                <h4 className="text-xs font-bold text-slate-200">کالبدشکافی دقیق علت رخداد باگ:</h4>
                <p className="text-xs text-slate-300 leading-relaxed">
                  {activeBug.problemExplanationFa}
                </p>
              </div>

              {/* Real CSV Evidence */}
              <div className="p-3.5 bg-slate-900/90 border border-slate-800 space-y-1.5">
                <div className="text-xs font-bold text-sky-400 flex items-center gap-1.5">
                  <Database className="w-3.5 h-3.5" />
                  <span>سند و شواهد واقعی در فایل‌های پیوست‌شده شما:</span>
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">{activeBug.csvEvidence}</p>
              </div>

              {/* Side-by-Side Code Comparison */}
              <div className="grid grid-cols-1 gap-4">
                <div className="space-y-1.5">
                  <div className="text-xs font-bold text-rose-400">
                    کد قبلی (دارای باگ در پروژه فعلی):
                  </div>
                  <pre
                    dir="ltr"
                    className="p-3.5 bg-slate-950 border border-rose-900/40 text-xs font-mono text-rose-200 overflow-x-auto leading-relaxed"
                  >
                    <code>{activeBug.buggyCodeSnippet}</code>
                  </pre>
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-emerald-400">
                      کد اصلاح‌شده و استاندارد (PolyBet v2.0):
                    </span>
                    <button
                      type="button"
                      onClick={() => handleCopy(activeBug.fixedCodeSnippet, activeBug.id)}
                      className="inline-flex items-center gap-1 px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 border border-slate-700"
                    >
                      {copiedKey === activeBug.id ? (
                        <>
                          <Check className="w-3.5 h-3.5 text-emerald-400" />
                          <span>کپی شد</span>
                        </>
                      ) : (
                        <>
                          <Copy className="w-3.5 h-3.5" />
                          <span>کپی قطعه کد</span>
                        </>
                      )}
                    </button>
                  </div>
                  <pre
                    dir="ltr"
                    className="p-3.5 bg-slate-950 border border-emerald-900/40 text-xs font-mono text-emerald-200 overflow-x-auto leading-relaxed"
                  >
                    <code>{activeBug.fixedCodeSnippet}</code>
                  </pre>
                </div>
              </div>

              {/* Architectural Upgrade Note */}
              <div className="p-3.5 bg-emerald-950/20 border border-emerald-800/40 flex items-start gap-3">
                <Wrench className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                <div className="text-xs">
                  <span className="font-bold text-emerald-300">ارتقای معماری اعمال‌شده: </span>
                  <span className="text-slate-200">{activeBug.architecturalUpgradeFa}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      ) : (
        /* GitHub Repository File Tree & Code Viewer */
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-4 border border-slate-800 bg-[#0F1623] divide-y divide-slate-800 max-h-[700px] overflow-y-auto">
            {fixedFiles.map((file, idx) => (
              <button
                key={file.pathInRepo}
                type="button"
                onClick={() => setSelectedFileIndex(idx)}
                className={`w-full text-right p-3.5 transition-colors space-y-1 ${
                  selectedFileIndex === idx ? 'bg-slate-800/80' : 'hover:bg-slate-900/60'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs font-bold text-emerald-400 truncate" dir="ltr">
                    {file.pathInRepo}
                  </span>
                  <span className="text-[11px] font-mono text-slate-400 shrink-0">
                    v2.0
                  </span>
                </div>
                <p className="text-xs text-slate-300 leading-snug">{file.descriptionFa}</p>
              </button>
            ))}
          </div>

          {activeFile && (
            <div className="lg:col-span-8 border border-slate-800 bg-[#0F1623] p-5 space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
                <div>
                  <h3 className="text-sm font-bold font-mono text-emerald-400" dir="ltr">
                    {activeFile.pathInRepo}
                  </h3>
                  <p className="text-xs text-slate-300 mt-0.5">{activeFile.descriptionFa}</p>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <button
                    type="button"
                    onClick={() => handleCopy(activeFile.code, activeFile.pathInRepo)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 border border-slate-700"
                  >
                    {copiedKey === activeFile.pathInRepo ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                        <span>کپی شد</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5" />
                        <span>کپی محتوای فایل</span>
                      </>
                    )}
                  </button>

                  <button
                    type="button"
                    onClick={() => handleDownloadFile(activeFile)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs text-emerald-400 border border-emerald-700/50 font-medium"
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span dir="ltr">Download {activeFile.filename}</span>
                  </button>
                </div>
              </div>

              <pre
                dir="ltr"
                className="p-4 bg-slate-950 border border-slate-800 text-xs font-mono text-slate-200 overflow-x-auto leading-relaxed max-h-[600px]"
              >
                <code>{activeFile.code}</code>
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
