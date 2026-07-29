import { useAIStore } from '../store/aiStore';
import { useState, useEffect, useCallback } from 'react';
import type { AIProvider, AIProviderConnectionCheck } from '../types/project';
import { useEditorStore } from '../store/editorStore';
import { Bot, Cloud, Brain, Sparkles, RefreshCw, Route, ShieldCheck, Copy, CheckCircle2, AlertCircle, Download, ExternalLink, MonitorCheck } from 'lucide-react';
import { RELEASE_LINKS, SCRIPTCUT_VERSION } from '../utils/releaseInfo';
import { buildSupportReport } from '../utils/supportReport';

const AI_PROVIDERS: AIProvider[] = ['ollama', 'openai', 'claude', 'xai', '9router'];
type TestableCloudProvider = 'openai' | 'xai';

const providerLabels: Record<AIProvider, string> = {
  ollama: 'Ollama',
  openai: 'OpenAI',
  claude: 'Claude',
  xai: 'Grok',
  '9router': '9router',
};

export default function SettingsPanel() {
  const {
    providers,
    providerChecks,
    defaultProvider,
    setProviderConfig,
    setProviderCheck,
    setDefaultProvider,
  } = useAIStore();
  const { backendUrl } = useEditorStore();
  const [ollamaModels, setOllamaModels] = useState<string[]>([]);
  const [nineRouterModels, setNineRouterModels] = useState<string[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [loadingNineRouterModels, setLoadingNineRouterModels] = useState(false);
  const [ollamaStatus, setOllamaStatus] = useState<{ ok: boolean; message: string } | null>(null);
  const [nineRouterStatus, setNineRouterStatus] = useState<{ ok: boolean; message: string } | null>(null);
  const [checkingCloudProvider, setCheckingCloudProvider] = useState<TestableCloudProvider | null>(null);
  const [copiedCommand, setCopiedCommand] = useState('');
  const [supportReportStatus, setSupportReportStatus] = useState<'idle' | 'copying' | 'copied' | 'error'>('idle');

  const fetchOllamaModels = useCallback(async () => {
    setLoadingModels(true);
    try {
      const baseUrl = providers.ollama.baseUrl || 'http://localhost:11434';
      const query = new URLSearchParams({ base_url: baseUrl });
      const [modelsRes, statusRes] = await Promise.all([
        fetch(`${backendUrl}/ai/ollama-models?${query.toString()}`),
        fetch(`${backendUrl}/ai/ollama-status?${query.toString()}`),
      ]);

      if (statusRes.ok) {
        const statusData = await statusRes.json();
        setOllamaStatus({ ok: !!statusData.ok, message: statusData.message || '' });
      } else {
        setOllamaStatus({ ok: false, message: 'Could not reach Ollama status endpoint.' });
      }

      if (modelsRes.ok) {
        const data = await modelsRes.json();
        setOllamaModels(data.models || []);
      } else {
        setOllamaModels([]);
      }
    } catch {
      setOllamaModels([]);
      setOllamaStatus({ ok: false, message: 'Could not connect to the configured Ollama URL.' });
    } finally {
      setLoadingModels(false);
    }
  }, [backendUrl, providers.ollama.baseUrl]);

  useEffect(() => {
    fetchOllamaModels();
  }, [fetchOllamaModels]);

  const fetchNineRouterModels = useCallback(async () => {
    setLoadingNineRouterModels(true);
    try {
      const config = providers['9router'];
      const res = await fetch(`${backendUrl}/ai/9router-models`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          base_url: config.baseUrl || 'http://localhost:20128/v1',
          api_key: config.apiKey || undefined,
        }),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => null);
        throw new Error(errorData?.detail || 'Could not load 9router models.');
      }

      const data = await res.json();
      const models = data.models || [];
      setNineRouterModels(models);
      setNineRouterStatus({
        ok: models.length > 0,
        message: models.length > 0 ? `Loaded ${models.length} 9router models.` : '9router returned no models.',
      });
    } catch (err) {
      setNineRouterModels([]);
      setNineRouterStatus({
        ok: false,
        message: err instanceof Error ? err.message : 'Could not load 9router models.',
      });
    } finally {
      setLoadingNineRouterModels(false);
    }
  }, [backendUrl, providers]);

  useEffect(() => {
    fetchNineRouterModels();
  }, [fetchNineRouterModels]);

  const checkCloudProvider = useCallback(async (provider: TestableCloudProvider) => {
    const config = providers[provider];
    setCheckingCloudProvider(provider);
    try {
      const response = await fetch(`${backendUrl}/ai/provider-check`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider,
          api_key: config.apiKey || undefined,
          model: config.model || undefined,
          base_url: config.baseUrl || undefined,
        }),
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.detail || `Connection test failed: ${response.statusText}`);
      }
      const result = (await response.json()) as AIProviderConnectionCheck;
      setProviderCheck(provider, result);
    } catch (error) {
      setProviderCheck(provider, {
        ok: false,
        authenticated: false,
        provider,
        code: 'local_backend_error',
        message: error instanceof Error ? error.message : 'Could not run the connection test.',
        models: [],
      });
    } finally {
      setCheckingCloudProvider(null);
    }
  }, [backendUrl, providers, setProviderCheck]);

  const updateCloudConfig = (
    provider: TestableCloudProvider,
    config: Parameters<typeof setProviderConfig>[1],
  ) => {
    setProviderConfig(provider, config);
  };

  const providerIcons: Record<AIProvider, React.ReactNode> = {
    ollama: <Bot className="w-4 h-4" />,
    openai: <Cloud className="w-4 h-4" />,
    claude: <Brain className="w-4 h-4" />,
    xai: <Sparkles className="w-4 h-4" />,
    '9router': <Route className="w-4 h-4" />,
  };

  const providerStatus: Record<AIProvider, { ok: boolean; label: string; local: boolean }> = {
    ollama: {
      ok: !!ollamaStatus?.ok,
      label: ollamaStatus?.ok ? 'Local ready' : 'Local offline',
      local: true,
    },
    openai: {
      ok: !!providerChecks.openai?.ok,
      label: providerChecks.openai?.ok
        ? 'Connection verified'
        : providerChecks.openai
          ? 'Connection failed'
          : providers.openai.apiKey
            ? 'Key not tested'
            : 'Needs key',
      local: false,
    },
    claude: {
      ok: !!providers.claude.apiKey,
      label: providers.claude.apiKey ? 'Key saved' : 'Needs key',
      local: false,
    },
    xai: {
      ok: !!providerChecks.xai?.ok,
      label: providerChecks.xai?.ok
        ? 'Connection verified'
        : providerChecks.xai
          ? 'Connection failed'
          : providers.xai.apiKey
            ? 'Key not tested'
            : 'Needs key',
      local: false,
    },
    '9router': {
      ok: !!nineRouterStatus?.ok,
      label: nineRouterStatus?.ok
        ? isLocalUrl(providers['9router'].baseUrl || '')
          ? 'Local route ready'
          : 'Remote route ready'
        : 'Route not verified',
      local: isLocalUrl(providers['9router'].baseUrl || ''),
    },
  };
  const activeStatus = providerStatus[defaultProvider];

  const copyCommand = useCallback(async (command: string) => {
    await navigator.clipboard?.writeText(command);
    setCopiedCommand(command);
    window.setTimeout(() => setCopiedCommand(''), 1500);
  }, []);

  const copySupportReport = useCallback(async () => {
    setSupportReportStatus('copying');
    const getJson = async (path: string) => {
      try {
        const response = await fetch(`${backendUrl}${path}`);
        return response.ok ? await response.json() : undefined;
      } catch {
        return undefined;
      }
    };

    try {
      const [runtime, recentJobs, app] = await Promise.all([
        getJson('/system/diagnostics'),
        getJson('/jobs/recent?kind=export&limit=3'),
        window.electronAPI?.getAppInfo?.().catch(() => undefined),
      ]);
      const report = buildSupportReport({
        fallbackVersion: SCRIPTCUT_VERSION,
        app,
        runtime,
        jobs: recentJobs?.jobs || [],
      });
      await navigator.clipboard.writeText(report);
      setSupportReportStatus('copied');
      window.setTimeout(() => setSupportReportStatus('idle'), 1800);
    } catch {
      setSupportReportStatus('error');
    }
  }, [backendUrl]);

  return (
    <div className="p-4 space-y-6">
      <h3 className="text-sm font-semibold">AI Settings</h3>

      <div className="space-y-3 rounded-lg border border-editor-border bg-editor-surface p-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 text-xs font-medium">
              <MonitorCheck className="w-4 h-4 text-editor-accent" />
              ScriptCut desktop
            </div>
            <p className="mt-1 text-[11px] leading-relaxed text-editor-text-muted">
              Version {SCRIPTCUT_VERSION}. Desktop releases are the recommended user path because they provide native file access, autosave, and bundled export tools.
            </p>
          </div>
          <span className="rounded bg-editor-bg px-2 py-1 text-[10px] text-editor-text-muted">
            {window.electronAPI ? 'Desktop' : 'Browser'}
          </span>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <ReleaseLink href={RELEASE_LINKS.latestRelease} icon={<Download className="h-3.5 w-3.5" />} label="Latest release" />
          <ReleaseLink href={RELEASE_LINKS.installGuide} icon={<ExternalLink className="h-3.5 w-3.5" />} label="Install guide" />
          <ReleaseLink href={RELEASE_LINKS.troubleshooting} icon={<ExternalLink className="h-3.5 w-3.5" />} label="Fix setup" />
          <ReleaseLink href={RELEASE_LINKS.issues} icon={<ExternalLink className="h-3.5 w-3.5" />} label="Report issue" />
        </div>
        <div className="flex items-center justify-between gap-2 rounded border border-editor-border bg-editor-bg px-2 py-2">
          <span className="text-[10px] text-editor-text-muted">Copy a redacted support report before reporting an export issue.</span>
          <div className="flex shrink-0 gap-1">
            <button
              onClick={copySupportReport}
              disabled={supportReportStatus === 'copying'}
              className="inline-flex items-center gap-1 rounded bg-editor-border px-2 py-1 text-[10px] text-editor-text-muted hover:bg-editor-surface disabled:opacity-50"
            >
              {supportReportStatus === 'copied' ? <CheckCircle2 className="h-3 w-3 text-editor-success" /> : <Copy className="h-3 w-3" />}
              {supportReportStatus === 'copying' ? 'Preparing' : supportReportStatus === 'copied' ? 'Copied' : 'Copy report'}
            </button>
            <a
              href={RELEASE_LINKS.bugReport}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 rounded bg-editor-border px-2 py-1 text-[10px] text-editor-text-muted hover:bg-editor-surface"
            >
              <ExternalLink className="h-3 w-3" /> Bug form
            </a>
          </div>
        </div>
        {supportReportStatus === 'error' && (
          <p className="text-[10px] text-editor-warning">Could not copy the report. Check clipboard permissions and try again.</p>
        )}
      </div>

      <div className="space-y-2 rounded-lg border border-editor-border bg-editor-surface p-3">
        <div className="flex items-center gap-2 text-xs font-medium">
          <ShieldCheck className="w-4 h-4 text-editor-success" />
          Local-first privacy
        </div>
        <p className="text-[11px] leading-relaxed text-editor-text-muted">
          Media files, project files, waveform data, and exports stay on this machine. Transcript
          text is sent only when you run AI actions with a cloud provider. Ollama and 9router can
          run against local endpoints.
        </p>
      </div>

      {/* Default provider selector */}
      <div className="space-y-2">
        <label className="text-xs text-editor-text-muted font-medium">Default AI Provider</label>
        <div className="grid grid-cols-5 gap-1.5">
          {AI_PROVIDERS.map((p) => (
            <button
              key={p}
              onClick={() => setDefaultProvider(p)}
              title={providerStatus[p].label}
              className={`flex flex-col items-center gap-1 p-2 rounded-lg border transition-colors text-[10px] ${
                defaultProvider === p
                  ? 'border-editor-accent bg-editor-accent/10 text-editor-accent'
                  : 'border-editor-border text-editor-text-muted hover:text-editor-text'
              }`}
            >
              {providerIcons[p]}
              {providerLabels[p]}
              <span className={`flex items-center gap-1 ${providerStatus[p].ok ? 'text-editor-success' : 'text-editor-warning'}`}>
                <span className={`h-1.5 w-1.5 rounded-full ${providerStatus[p].ok ? 'bg-editor-success' : 'bg-editor-warning'}`} />
                {providerStatus[p].local ? 'Local' : 'Cloud'}
              </span>
            </button>
          ))}
        </div>
        <div
          className={`rounded border px-3 py-2 text-[11px] ${
            activeStatus.ok
              ? 'border-editor-success/30 bg-editor-success/10 text-editor-success'
              : 'border-editor-warning/30 bg-editor-warning/10 text-editor-warning'
          }`}
        >
          <div className="flex items-center justify-between gap-2">
            <span className="font-medium">
              {providerLabels[defaultProvider]}: {activeStatus.label}
            </span>
            <span>{activeStatus.local ? 'Local endpoint' : 'Cloud endpoint'}</span>
          </div>
          <p className="mt-1 leading-relaxed text-editor-text-muted">
            {activeStatus.local
              ? 'AI transcript actions stay on your configured local endpoint when this provider is selected.'
              : `AI Editor will use only ${providerLabels[defaultProvider]}. Keys saved under other providers are not used until you select them here.`}
          </p>
        </div>
      </div>

      {/* Ollama settings */}
      <ProviderSection title="Ollama (Local)" icon={providerIcons.ollama}>
        <ProviderNote>Runs through your configured local Ollama server.</ProviderNote>
        <InputField
          label="Base URL"
          value={providers.ollama.baseUrl || ''}
          onChange={(v) => setProviderConfig('ollama', { baseUrl: v })}
          placeholder="http://localhost:11434"
        />
        {ollamaStatus && (
          <p className={`text-[11px] ${ollamaStatus.ok ? 'text-editor-success' : 'text-editor-warning'}`}>
            {ollamaStatus.message}
          </p>
        )}
        {!ollamaStatus?.ok && (
          <SetupCommands
            commands={[
              'ollama serve',
              `ollama pull ${providers.ollama.model || 'llama3'}`,
            ]}
            copiedCommand={copiedCommand}
            onCopy={copyCommand}
          />
        )}
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <label className="text-xs text-editor-text-muted">Model</label>
            <button
              onClick={fetchOllamaModels}
              disabled={loadingModels}
              className="text-[10px] text-editor-accent hover:underline flex items-center gap-0.5"
            >
              <RefreshCw className={`w-2.5 h-2.5 ${loadingModels ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
          {ollamaModels.length > 0 ? (
            <select
              value={providers.ollama.model}
              onChange={(e) => setProviderConfig('ollama', { model: e.target.value })}
              className="w-full px-3 py-2 bg-editor-surface border border-editor-border rounded-lg text-xs text-editor-text focus:outline-none focus:border-editor-accent"
            >
              {ollamaModels.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          ) : (
            <>
              <InputField
                label=""
                value={providers.ollama.model}
                onChange={(v) => setProviderConfig('ollama', { model: v })}
                placeholder="llama3"
              />
              {ollamaStatus?.ok && (
                <SetupCommands
                  commands={[`ollama pull ${providers.ollama.model || 'llama3'}`]}
                  copiedCommand={copiedCommand}
                  onCopy={copyCommand}
                />
              )}
            </>
          )}
        </div>
      </ProviderSection>

      {/* OpenAI settings */}
      <ProviderSection title="OpenAI" icon={providerIcons.openai}>
        <ProviderNote>AI actions send transcript text to OpenAI when this provider is selected.</ProviderNote>
        <CloudConnectionControls
          active={defaultProvider === 'openai'}
          loading={checkingCloudProvider === 'openai'}
          status={providerChecks.openai}
          keyUrl="https://platform.openai.com/api-keys"
          providerLabel="OpenAI"
          onActivate={() => setDefaultProvider('openai')}
          onTest={() => void checkCloudProvider('openai')}
        />
        <InputField
          label="API Key"
          value={providers.openai.apiKey || ''}
          onChange={(v) => updateCloudConfig('openai', { apiKey: v })}
          placeholder="sk-..."
          type="password"
        />
        <InputField
          label="Model"
          value={providers.openai.model}
          onChange={(v) => updateCloudConfig('openai', { model: v })}
          placeholder="gpt-4o"
          suggestions={providerChecks.openai?.models}
        />
        <ProviderNote>
          ChatGPT Plus/Pro and OpenAI API billing are separate. The connection test sends no transcript and uses no completion tokens.
        </ProviderNote>
      </ProviderSection>

      {/* Claude settings */}
      <ProviderSection title="Claude (Anthropic)" icon={providerIcons.claude}>
        <ProviderNote>AI actions send transcript text to Anthropic when this provider is selected.</ProviderNote>
        <InputField
          label="API Key"
          value={providers.claude.apiKey || ''}
          onChange={(v) => setProviderConfig('claude', { apiKey: v })}
          placeholder="sk-ant-..."
          type="password"
        />
        <InputField
          label="Model"
          value={providers.claude.model}
          onChange={(v) => setProviderConfig('claude', { model: v })}
          placeholder="claude-sonnet-4-20250514"
        />
      </ProviderSection>

      <ProviderSection title="Grok (xAI)" icon={providerIcons.xai}>
        <ProviderNote>AI actions send transcript text to the official xAI API when this provider is selected.</ProviderNote>
        <CloudConnectionControls
          active={defaultProvider === 'xai'}
          loading={checkingCloudProvider === 'xai'}
          status={providerChecks.xai}
          keyUrl="https://console.x.ai/"
          providerLabel="Grok"
          onActivate={() => setDefaultProvider('xai')}
          onTest={() => void checkCloudProvider('xai')}
        />
        <InputField
          label="API Key"
          value={providers.xai.apiKey || ''}
          onChange={(v) => updateCloudConfig('xai', { apiKey: v })}
          placeholder="xai-..."
          type="password"
        />
        <InputField
          label="Model"
          value={providers.xai.model}
          onChange={(v) => updateCloudConfig('xai', { model: v })}
          placeholder="grok-4.5"
          suggestions={providerChecks.xai?.models}
        />
        <ProviderNote>
          The xAI key must allow the Models and Chat endpoints plus the selected model. The connection test sends no transcript.
        </ProviderNote>
      </ProviderSection>

      {/* 9router settings */}
      <ProviderSection title="9router" icon={providerIcons['9router']}>
        <ProviderNote>Uses the configured 9router-compatible endpoint; local endpoints keep traffic local.</ProviderNote>
        <InputField
          label="Base URL"
          value={providers['9router'].baseUrl || ''}
          onChange={(v) => setProviderConfig('9router', { baseUrl: v })}
          placeholder="http://localhost:20128/v1"
        />
        <InputField
          label="API Key"
          value={providers['9router'].apiKey || ''}
          onChange={(v) => setProviderConfig('9router', { apiKey: v })}
          placeholder="sk-..."
          type="password"
        />
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <label className="text-xs text-editor-text-muted">Model</label>
            <button
              onClick={fetchNineRouterModels}
              disabled={loadingNineRouterModels}
              className="text-[10px] text-editor-accent hover:underline flex items-center gap-0.5"
            >
              <RefreshCw className={`w-2.5 h-2.5 ${loadingNineRouterModels ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
          {nineRouterStatus && (
            <p className={`text-[11px] ${nineRouterStatus.ok ? 'text-editor-success' : 'text-editor-warning'}`}>
              {nineRouterStatus.message}
            </p>
          )}
          {nineRouterModels.length > 0 && (
            <select
              value={nineRouterModels.includes(providers['9router'].model) ? providers['9router'].model : ''}
              onChange={(e) => {
                if (e.target.value) setProviderConfig('9router', { model: e.target.value });
              }}
              className="w-full px-3 py-2 bg-editor-surface border border-editor-border rounded-lg text-xs text-editor-text focus:outline-none focus:border-editor-accent"
            >
              <option value="">Custom model</option>
              {nineRouterModels.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          )}
          <InputField
            label={nineRouterModels.length > 0 ? 'Custom Model' : ''}
            value={providers['9router'].model}
            onChange={(v) => setProviderConfig('9router', { model: v })}
            placeholder="gpt-4o"
          />
        </div>
      </ProviderSection>
    </div>
  );
}

function ReleaseLink({ href, icon, label }: { href: string; icon: React.ReactNode; label: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="inline-flex min-w-0 items-center justify-center gap-1.5 rounded border border-editor-border bg-editor-bg px-2 py-1.5 text-[11px] text-editor-text-muted hover:text-editor-text"
    >
      {icon}
      <span className="truncate">{label}</span>
    </a>
  );
}

function ProviderNote({ children }: { children: React.ReactNode }) {
  return <p className="text-[11px] leading-relaxed text-editor-text-muted">{children}</p>;
}

function CloudConnectionControls({
  active,
  loading,
  status,
  keyUrl,
  providerLabel,
  onActivate,
  onTest,
}: {
  active: boolean;
  loading: boolean;
  status?: AIProviderConnectionCheck;
  keyUrl: string;
  providerLabel: string;
  onActivate: () => void;
  onTest: () => void;
}) {
  return (
    <div className="space-y-2 rounded border border-editor-border bg-editor-bg p-2">
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={onActivate}
          className={`rounded px-2 py-1 text-[10px] font-medium ${
            active
              ? 'bg-editor-accent/15 text-editor-accent'
              : 'bg-editor-surface text-editor-text-muted hover:text-editor-text'
          }`}
        >
          {active ? `Active for AI Editor: ${providerLabel}` : `Use ${providerLabel} in AI Editor`}
        </button>
        <button
          type="button"
          onClick={onTest}
          disabled={loading}
          className="inline-flex items-center gap-1 rounded bg-editor-border px-2 py-1 text-[10px] text-editor-text-muted hover:text-editor-text disabled:opacity-50"
        >
          <RefreshCw className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} />
          {loading ? 'Testing' : 'Test connection'}
        </button>
      </div>
      {status && (
        <div
          className={`rounded border px-2 py-1.5 text-[10px] leading-relaxed ${
            status.ok
              ? 'border-editor-success/30 bg-editor-success/10 text-editor-success'
              : status.authenticated
                ? 'border-editor-warning/30 bg-editor-warning/10 text-editor-warning'
                : 'border-editor-danger/30 bg-editor-danger/10 text-editor-danger'
          }`}
        >
          {status.message}
        </div>
      )}
      <a
        href={keyUrl}
        target="_blank"
        rel="noreferrer"
        className="inline-flex items-center gap-1 text-[10px] text-editor-accent hover:underline"
      >
        <ExternalLink className="h-3 w-3" />
        Create or manage API key
      </a>
    </div>
  );
}

function SetupCommands({
  commands,
  copiedCommand,
  onCopy,
}: {
  commands: string[];
  copiedCommand: string;
  onCopy: (command: string) => void;
}) {
  return (
    <div className="space-y-1 rounded border border-editor-border bg-editor-bg p-2">
      <div className="flex items-center gap-1 text-[10px] font-medium text-editor-text-muted">
        <AlertCircle className="h-3 w-3 text-editor-warning" />
        Local setup
      </div>
      {commands.map((command) => (
        <button
          key={command}
          onClick={() => onCopy(command)}
          className="flex w-full items-center justify-between gap-2 rounded bg-editor-surface px-2 py-1 text-left font-mono text-[10px] text-editor-text-muted hover:text-editor-text"
        >
          <span className="truncate">{command}</span>
          {copiedCommand === command ? (
            <CheckCircle2 className="h-3 w-3 shrink-0 text-editor-success" />
          ) : (
            <Copy className="h-3 w-3 shrink-0" />
          )}
        </button>
      ))}
    </div>
  );
}

function isLocalUrl(url: string) {
  return /^(https?:\/\/)?(localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\])/i.test(url.trim());
}

function ProviderSection({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-3 p-3 bg-editor-surface rounded-lg">
      <div className="flex items-center gap-2 text-xs font-medium">
        {icon}
        {title}
      </div>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function InputField({
  label,
  value,
  onChange,
  placeholder,
  type = 'text',
  suggestions,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  type?: string;
  suggestions?: string[];
}) {
  const listId = suggestions?.length
    ? `models-${label.toLowerCase().replace(/[^a-z0-9]+/g, '-')}-${placeholder.replace(/[^a-z0-9]+/gi, '-')}`
    : undefined;
  return (
    <div className="space-y-1">
      {label && <label className="text-xs text-editor-text-muted">{label}</label>}
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        list={listId}
        className="w-full px-3 py-2 bg-editor-bg border border-editor-border rounded-lg text-xs text-editor-text placeholder:text-editor-text-muted/50 focus:outline-none focus:border-editor-accent"
      />
      {listId && (
        <datalist id={listId}>
          {suggestions?.map((suggestion) => <option key={suggestion} value={suggestion} />)}
        </datalist>
      )}
    </div>
  );
}
