import { FormEvent, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/controlPlane'

interface Props { paused: boolean }

export default function PromptLibrary({ paused: _paused }: Props) {
  const queryClient = useQueryClient()
  const { data: prompts = [], isLoading: promptsLoading } = useQuery({
    queryKey: ['prompts'],
    queryFn: api.prompts,
  })
  const [selectedName, setSelectedName] = useState<string | null>(null)

  const selectedPrompt = useMemo(
    () => prompts.find((p) => p.name === selectedName) ?? null,
    [prompts, selectedName]
  )

  const { data: versions = [], isLoading: versionsLoading } = useQuery({
    queryKey: ['prompt-versions', selectedName],
    queryFn: () => api.promptVersions(selectedName as string),
    enabled: Boolean(selectedName),
  })

  const [name, setName] = useState('')
  const [environment, setEnvironment] = useState('default')
  const [labels, setLabels] = useState('')
  const [promptText, setPromptText] = useState('')
  const [createdBy, setCreatedBy] = useState('dashboard')
  const [activateOnCreate, setActivateOnCreate] = useState(true)

  const createMutation = useMutation({
    mutationFn: api.createPromptVersion,
    onSuccess: (created) => {
      setSelectedName(created.name)
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
      queryClient.invalidateQueries({ queryKey: ['prompt-versions', created.name] })
      setPromptText('')
    },
  })

  const activateMutation = useMutation({
    mutationFn: ({ targetName, version, env }: { targetName: string; version: number; env: string }) =>
      api.activatePromptVersion(targetName, version, env),
    onSuccess: (_data, vars) => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
      queryClient.invalidateQueries({ queryKey: ['prompt-versions', vars.targetName] })
    },
  })

  const importMutation = useMutation({
    mutationFn: api.importPromptsFromSource,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
      if (selectedName) {
        queryClient.invalidateQueries({ queryKey: ['prompt-versions', selectedName] })
      }
    },
  })

  const onCreate = (e: FormEvent) => {
    e.preventDefault()
    const finalName = (selectedName || name).trim()
    if (!finalName || !promptText.trim()) return
    createMutation.mutate({
      name: finalName,
      prompt: promptText.trim(),
      environment: environment.trim() || 'default',
      labels: labels.split(',').map((l) => l.trim()).filter(Boolean),
      config: {},
      created_by: createdBy.trim() || 'dashboard',
      activate: activateOnCreate,
    })
  }

  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
      <div className="card xl:col-span-1">
        <div className="flex items-center justify-between mb-2">
          <div className="card-title mb-0">Prompt Definitions</div>
          <button
            type="button"
            className="px-2 py-1 rounded border border-border text-sub text-xs hover:bg-white/5 disabled:opacity-50"
            onClick={() => importMutation.mutate()}
            disabled={importMutation.isPending}
            title="Import prompts from project source files"
          >
            {importMutation.isPending ? 'Importing...' : 'Import Source'}
          </button>
        </div>
        {importMutation.isSuccess && (
          <div className="text-[11px] text-green mb-2">
            Imported {importMutation.data.imported} prompts from {importMutation.data.scanned_files} files.
          </div>
        )}
        {importMutation.isError && (
          <div className="text-[11px] text-red mb-2">Source import failed.</div>
        )}
        {promptsLoading ? (
          <div className="text-xs text-sub">Loading prompts...</div>
        ) : prompts.length === 0 ? (
          <div className="text-xs text-sub">No prompts yet. Create your first one.</div>
        ) : (
          <div className="space-y-2 max-h-[65vh] overflow-auto pr-1">
            {prompts.map((p) => (
              <button
                key={p.name}
                type="button"
                onClick={() => {
                  setSelectedName(p.name)
                  setName(p.name)
                  setPromptText('')
                }}
                className={`w-full text-left rounded border p-2 ${
                  selectedName === p.name ? 'border-cyan bg-white/5' : 'border-border hover:bg-white/5'
                }`}
              >
                <div className="text-sm text-white font-mono">{p.name}</div>
                <div className="text-[11px] text-sub">latest v{p.latest_version} · env {p.latest_environment}</div>
                <div className="text-[11px] text-sub mt-1">{p.latest_preview || '-'}</div>
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="card xl:col-span-2 space-y-5">
        {selectedName && versions.length > 0 && (() => {
          const activeVersion = versions.find((v) => v.is_active) ?? versions[versions.length - 1]
          return (
            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="card-title mb-0">{selectedName}</div>
                <div className="text-[11px] text-sub">
                  v{activeVersion.version} · {activeVersion.environment} · {activeVersion.is_active ? 'Active' : 'Inactive'}
                </div>
              </div>
              <div className="text-[10px] text-gray-500 mb-1">
                Created by {activeVersion.created_by} · {activeVersion.created_at}
              </div>
              {activeVersion.labels.length > 0 && (
                <div className="flex gap-1 mb-2">
                  {activeVersion.labels.map((l) => (
                    <span key={l} className="px-1.5 py-0.5 rounded bg-white/5 border border-border text-[10px] text-sub">{l}</span>
                  ))}
                </div>
              )}
              <pre className="w-full bg-bg border border-border rounded px-3 py-2 text-xs text-gray-300 font-mono whitespace-pre-wrap break-words max-h-[40vh] overflow-auto">
                {activeVersion.prompt}
              </pre>
            </div>
          )
        })()}

        <div>
        <div className="card-title">Create New Prompt Version</div>
        <form className="space-y-3" onSubmit={onCreate}>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <input
              className="bg-bg border border-border rounded px-2 py-1.5 text-xs text-text"
              placeholder="Prompt name"
              value={selectedName ?? name}
              onChange={(e) => {
                setSelectedName(null)
                setName(e.target.value)
              }}
            />
            <input
              className="bg-bg border border-border rounded px-2 py-1.5 text-xs text-text"
              placeholder="Environment (default/prod)"
              value={environment}
              onChange={(e) => setEnvironment(e.target.value)}
            />
            <input
              className="bg-bg border border-border rounded px-2 py-1.5 text-xs text-text"
              placeholder="Created by"
              value={createdBy}
              onChange={(e) => setCreatedBy(e.target.value)}
            />
          </div>
          <input
            className="w-full bg-bg border border-border rounded px-2 py-1.5 text-xs text-text"
            placeholder="Labels (comma separated)"
            value={labels}
            onChange={(e) => setLabels(e.target.value)}
          />
          <textarea
            className="w-full min-h-[170px] bg-bg border border-border rounded px-2 py-2 text-xs text-text font-mono"
            placeholder="Write prompt template here..."
            value={promptText}
            onChange={(e) => setPromptText(e.target.value)}
          />
          <label className="flex items-center gap-2 text-xs text-sub">
            <input
              type="checkbox"
              checked={activateOnCreate}
              onChange={(e) => setActivateOnCreate(e.target.checked)}
            />
            Set this version as active for selected environment
          </label>
          <button
            type="submit"
            className="px-3 py-1.5 rounded border border-cyan text-cyan text-xs hover:bg-white/5"
            disabled={createMutation.isPending}
          >
            {createMutation.isPending ? 'Saving...' : 'Create Version'}
          </button>
          {createMutation.isError && <div className="text-xs text-red">Failed to create prompt version.</div>}
        </form>
        </div>

        <div>
          <div className="text-xs uppercase tracking-widest text-sub mb-2">
            {selectedPrompt ? `Versions · ${selectedPrompt.name}` : 'Versions'}
          </div>
          {!selectedName ? (
            <div className="text-xs text-sub">Select a prompt from the left to view versions.</div>
          ) : versionsLoading ? (
            <div className="text-xs text-sub">Loading versions...</div>
          ) : versions.length === 0 ? (
            <div className="text-xs text-sub">No versions yet.</div>
          ) : (
            <div className="overflow-x-auto border border-border rounded">
              <table className="w-full text-xs font-mono">
                <thead>
                  <tr className="border-b border-border text-gray-500">
                    <th className="text-left py-2 px-3">Version</th>
                    <th className="text-left py-2 px-3">Env</th>
                    <th className="text-left py-2 px-3">Active</th>
                    <th className="text-left py-2 px-3">Created</th>
                    <th className="text-left py-2 px-3">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {versions.map((v) => (
                    <tr key={`${v.name}-${v.version}-${v.environment}`} className="border-b border-border/50">
                      <td className="py-2 px-3 text-cyan">v{v.version}</td>
                      <td className="py-2 px-3 text-gray-300">{v.environment}</td>
                      <td className="py-2 px-3 text-gray-300">{v.is_active ? 'Yes' : 'No'}</td>
                      <td className="py-2 px-3 text-gray-400">{v.created_at}</td>
                      <td className="py-2 px-3">
                        <button
                          type="button"
                          className="px-2 py-1 rounded border border-border text-sub hover:bg-white/5 disabled:opacity-40"
                          disabled={v.is_active || activateMutation.isPending}
                          onClick={() => activateMutation.mutate({
                            targetName: v.name,
                            version: v.version,
                            env: v.environment,
                          })}
                        >
                          Activate
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
