"use client";

import { useEffect, useState } from "react";
import { Upload, FileText, CheckCircle2, RefreshCw, Trash2, Sparkles, AlertCircle } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface CvStatus {
  uploaded: boolean;
  filename: string | null;
  preview: string;
  fullText?: string;
  length: number;
}

interface ParsedProfile {
  fullName?: string;
  email?: string;
  phone?: string;
  location?: string;
  skills?: string[];
  yearsExperience?: number | string;
  languages?: string[];
}

export default function CvPage() {
  const [status, setStatus] = useState<CvStatus | null>(null);
  const [profile, setProfile] = useState<ParsedProfile | null>(null);
  const [uploading, setUploading] = useState(false);
  const [parsing, setParsing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [backendOk, setBackendOk] = useState(true);

  async function fetchStatus() {
    try {
      const r = await fetch(`${API}/cv`);
      if (!r.ok) {
        setBackendOk(false);
        return;
      }
      const data = await r.json();
      setStatus(data);
      setBackendOk(true);
    } catch {
      setBackendOk(false);
    }
  }

  async function fetchPrefs() {
    try {
      const r = await fetch(`${API}/settings/prefs`);
      if (!r.ok) return;
      const data = await r.json();
      setProfile({
        fullName: data.fullName,
        email: data.email,
        phone: data.phone,
        location: data.location,
        skills: data.preferredTech || [],
      });
    } catch { /* ignore */ }
  }

  useEffect(() => {
    fetchStatus();
    fetchPrefs();
  }, []);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const r = await fetch(`${API}/cv/upload`, {
        method: "POST",
        body: fd,
      });
      const data = await r.json();
      if (!r.ok) {
        throw new Error(data.detail || "Upload failed");
      }
      await fetchStatus();
      // Auto-parse after upload
      setUploading(false);
      setParsing(true);
      const parseR = await fetch(`${API}/cv/parse`, { method: "POST" });
      if (parseR.ok) {
        const parseData = await parseR.json();
        setProfile(parseData.profile);
      }
      await fetchPrefs();
    } catch (err: any) {
      setError(err.message || "Upload failed");
    } finally {
      setUploading(false);
      setParsing(false);
    }
  }

  async function handleReparse() {
    setParsing(true);
    setError(null);
    try {
      const r = await fetch(`${API}/cv/parse`, { method: "POST" });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || "Parse failed");
      setProfile(data.profile);
      await fetchPrefs();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setParsing(false);
    }
  }

  function handleRemove() {
    // No backend delete endpoint — just clear UI state. Re-uploading replaces it server-side.
    setStatus({ uploaded: false, filename: null, preview: "", length: 0 });
    setProfile(null);
  }

  if (!backendOk) {
    return (
      <div className="rounded-2xl glass p-8 text-center">
        <AlertCircle className="w-10 h-10 text-warn mx-auto mb-3" />
        <h2 className="font-serif text-2xl mb-2">Backend not reachable</h2>
        <p className="text-white/55 text-sm">
          Make sure FastAPI is running on <code className="text-warn">http://localhost:8000</code>.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <div className="label-mono mb-2">My CV</div>
        <h1 className="font-serif text-4xl tracking-tight">Resume & extracted profile</h1>
        <p className="text-white/55 mt-1 text-[15px]">
          The agent uses your CV to score job matches, fill forms, and write cover letters.
        </p>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Upload */}
        <div className="lg:col-span-2 rounded-2xl glass p-7">
          {!status?.uploaded ? (
            <label
              htmlFor="cv-upload"
              className="block border-2 border-dashed border-white/10 hover:border-accent/40 rounded-xl p-12 text-center cursor-pointer transition group"
            >
              <input
                id="cv-upload"
                type="file"
                accept=".pdf,.docx,.txt"
                onChange={handleUpload}
                disabled={uploading}
                className="hidden"
              />
              <div className="w-14 h-14 mx-auto rounded-2xl bg-gradient-to-br from-accent/20 to-electric/20 grid place-items-center mb-4 group-hover:shadow-glow transition">
                {uploading ? (
                  <RefreshCw className="w-6 h-6 text-accent animate-spin" />
                ) : (
                  <Upload className="w-6 h-6 text-accent" />
                )}
              </div>
              <div className="font-serif text-2xl mb-1">
                {uploading ? "Uploading..." : "Upload your CV"}
              </div>
              <div className="text-sm text-white/50">PDF, DOCX or TXT · max 10 MB</div>
              <div className="mt-6 inline-flex items-center gap-1.5 text-xs font-mono uppercase tracking-[0.18em] text-white/40">
                <span className="w-1 h-1 rounded-full bg-white/40" />
                Click or drop file
              </div>
            </label>
          ) : (
            <div>
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-accent/20 to-electric/20 grid place-items-center">
                  <FileText className="w-5 h-5 text-accent" />
                </div>
                <div className="flex-1">
                  <div className="font-serif text-xl">{status.filename || "uploaded.pdf"}</div>
                  <div className="text-xs font-mono text-white/40 mt-0.5">
                    {status.length.toLocaleString()} characters parsed
                  </div>
                  {parsing ? (
                    <div className="mt-3 inline-flex items-center gap-2 text-xs text-electric-glow">
                      <RefreshCw className="w-3 h-3 animate-spin" />
                      Parsing CV with AI…
                    </div>
                  ) : (
                    <div className="mt-3 inline-flex items-center gap-1.5 text-xs text-accent">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Profile extracted successfully
                    </div>
                  )}
                </div>
                <button
                  onClick={handleReparse}
                  disabled={parsing}
                  className="text-white/40 hover:text-electric transition p-2"
                  title="Re-parse with AI"
                >
                  <RefreshCw className={`w-4 h-4 ${parsing ? "animate-spin" : ""}`} />
                </button>
                <button
                  onClick={handleRemove}
                  className="text-white/40 hover:text-danger transition p-2"
                  title="Remove (re-upload to replace)"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>

              {(status.fullText || status.preview) && (
                <div className="mt-6 pt-6 border-t border-white/5">
                  <div className="flex items-center justify-between mb-2">
                    <div className="label-mono text-[10px] text-white/40">Full CV text</div>
                    <div className="text-[10px] font-mono text-white/35">
                      Showing {(status.fullText || status.preview).length.toLocaleString()} / {status.length.toLocaleString()} characters
                    </div>
                  </div>
                  <pre className="text-xs text-white/60 whitespace-pre-wrap font-mono leading-relaxed max-h-[520px] overflow-auto rounded-xl bg-black/20 border border-white/5 p-4">
                    {status.fullText || status.preview}
                  </pre>
                </div>
              )}

              {error && (
                <div className="mt-4 p-3 rounded-lg bg-danger/10 border border-danger/30 text-danger text-sm">
                  {error}
                </div>
              )}
            </div>
          )}
        </div>

        {/* AI Insights */}
        <div className="rounded-2xl glass p-6">
          <div className="flex items-center gap-2 mb-4">
            <Sparkles className="w-4 h-4 text-accent" />
            <div className="label-mono">AI Insights</div>
          </div>
          {profile ? (
            <div className="space-y-4 text-sm">
              {profile.fullName && (
                <Field label="Name" value={profile.fullName} />
              )}
              {profile.email && (
                <Field label="Email" value={profile.email} />
              )}
              {profile.location && (
                <Field label="Location" value={profile.location} />
              )}
              {profile.yearsExperience && (
                <Field label="Years of experience" value={String(profile.yearsExperience)} />
              )}
              {profile.languages && profile.languages.length > 0 && (
                <Field label="Languages" value={profile.languages.join(", ")} />
              )}
            </div>
          ) : (
            <div className="text-xs text-white/40">
              Upload a CV to extract profile.
            </div>
          )}
        </div>
      </div>

      {/* Skills */}
      {profile?.skills && profile.skills.length > 0 && (
        <div className="rounded-2xl glass p-7">
          <div className="label-mono mb-2">Extracted skills</div>
          <h2 className="font-serif text-2xl mb-5">Profile</h2>
          <div className="flex flex-wrap gap-2">
            {profile.skills.map((s, i) => (
              <span
                key={`${String(s).toLowerCase()}-${i}`}
                className="px-3 py-1.5 rounded-md bg-white/[0.04] border border-white/[0.06] text-sm"
              >
                {s}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="label-mono text-[10px] text-white/40 mb-0.5">{label}</div>
      <div className="text-white/85">{value}</div>
    </div>
  );
}
