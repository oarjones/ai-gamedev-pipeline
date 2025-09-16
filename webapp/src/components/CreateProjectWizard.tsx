import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppStore } from '@/store/appStore';
import { createProject, apiPost } from '@/lib/api';
import { ProjectManifest } from '@/types';

interface CreateProjectWizardProps {
  onClose: () => void;
}

export function CreateProjectWizard({ onClose }: CreateProjectWizardProps) {
  const navigate = useNavigate();
  const setProjectId = useAppStore((s) => s.setProjectId);
  const pushToast = useAppStore((s) => s.pushToast);

  const [step, setStep] = useState<'basic' | 'manifest' | 'generating'>('basic');
  const [loading, setLoading] = useState(false);

  // Project basic info
  const [projectName, setProjectName] = useState('');
  const [projectDescription, setProjectDescription] = useState('');

  // Manifest data
  const [manifest, setManifest] = useState<ProjectManifest>({
    name: '',
    pitch: '',
    genre: '',
    platform: '',
    art_style: '',
    target_audience: '',
    core_mechanics: [],
    technical_requirements: [],
    scope: ''
  });

  const updateManifest = <K extends keyof ProjectManifest>(key: K, value: ProjectManifest[K]) => {
    setManifest(prev => ({ ...prev, [key]: value }));
  };

  const handleBasicNext = () => {
    if (!projectName.trim()) {
      pushToast('El nombre del proyecto es requerido');
      return;
    }
    setManifest(prev => ({ ...prev, name: projectName }));
    setStep('manifest');
  };

  const handleManifestNext = async () => {
    if (!manifest.pitch || !manifest.genre || !manifest.art_style) {
      pushToast('Completa al menos Pitch, Género y Estilo visual');
      return;
    }

    setLoading(true);
    setStep('generating');

    try {
      // 1. Create project
      const project = await createProject({
        name: projectName,
        description: projectDescription,
        settings: {}
      });

      // 2. Select project
      setProjectId(project.id);

      // 3. Save manifest
      await apiPost(`/api/v1/projects/${project.id}/manifest`, manifest);

      // 4. Generate initial plan via AI agent
      await apiPost(`/api/v1/projects/${project.id}/plan/propose`, {
        context: `Nuevo proyecto de videojuego: ${manifest.name}

Pitch: ${manifest.pitch}
Género: ${manifest.genre}
Plataforma: ${manifest.platform || 'No especificada'}
Estilo visual: ${manifest.art_style}
Audiencia objetivo: ${manifest.target_audience || 'No especificada'}
Mecánicas core: ${manifest.core_mechanics?.join(', ') || 'No especificadas'}
Requerimientos técnicos: ${manifest.technical_requirements?.join(', ') || 'No especificados'}
Alcance: ${manifest.scope || 'No especificado'}

Genera un plan de desarrollo detallado con tareas, dependencias y fases de desarrollo.`
      });

      pushToast(`Proyecto "${project.name}" creado y plan inicial generado`);

      // 5. Navigate to consensus phase
      navigate(`/projects/${project.id}/consensus`);
      onClose();

    } catch (error: any) {
      pushToast(`Error: ${error.message}`);
      setStep('manifest'); // Go back to allow retry
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-hidden">
        <div className="flex items-center justify-between p-6 border-b">
          <h2 className="text-xl font-semibold">
            {step === 'basic' && 'Crear Nuevo Proyecto'}
            {step === 'manifest' && 'Definir Características del Juego'}
            {step === 'generating' && 'Generando Plan Inicial...'}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
            disabled={loading}
          >
            ✕
          </button>
        </div>

        <div className="p-6 overflow-y-auto">
          {step === 'basic' && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2">
                  Nombre del Proyecto *
                </label>
                <input
                  type="text"
                  className="w-full border rounded-md px-3 py-2"
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  placeholder="Mi Juego Increíble"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">
                  Descripción (opcional)
                </label>
                <textarea
                  className="w-full border rounded-md px-3 py-2 h-24"
                  value={projectDescription}
                  onChange={(e) => setProjectDescription(e.target.value)}
                  placeholder="Breve descripción del proyecto..."
                />
              </div>
            </div>
          )}

          {step === 'manifest' && (
            <div className="space-y-4 text-sm">
              <ManifestField
                label="Pitch del Juego"
                value={manifest.pitch || ''}
                onChange={(v) => updateManifest('pitch', v)}
                required
                textarea
                placeholder="Describe tu juego en 2-3 oraciones..."
              />
              <ManifestField
                label="Género"
                value={manifest.genre || ''}
                onChange={(v) => updateManifest('genre', v)}
                required
                placeholder="RPG, Plataformas, Estrategia..."
              />
              <ManifestField
                label="Plataforma"
                value={manifest.platform || ''}
                onChange={(v) => updateManifest('platform', v)}
                placeholder="PC, Mobile, Console..."
              />
              <ManifestField
                label="Estilo Visual"
                value={manifest.art_style || ''}
                onChange={(v) => updateManifest('art_style', v)}
                required
                placeholder="Pixel art, 3D realista, Low poly..."
              />
              <ManifestField
                label="Audiencia Objetivo"
                value={manifest.target_audience || ''}
                onChange={(v) => updateManifest('target_audience', v)}
                placeholder="Casual, Hardcore, Familiar..."
              />
              <ManifestField
                label="Mecánicas Core"
                value={manifest.core_mechanics?.join(', ') || ''}
                onChange={(v) => updateManifest('core_mechanics', v.split(',').map(s => s.trim()).filter(Boolean))}
                textarea
                placeholder="Salto, Combate, Crafting..."
              />
              <ManifestField
                label="Requerimientos Técnicos"
                value={manifest.technical_requirements?.join(', ') || ''}
                onChange={(v) => updateManifest('technical_requirements', v.split(',').map(s => s.trim()).filter(Boolean))}
                textarea
                placeholder="Unity 2023, Multiplayer, Save system..."
              />
              <ManifestField
                label="Alcance del Proyecto"
                value={manifest.scope || ''}
                onChange={(v) => updateManifest('scope', v)}
                textarea
                placeholder="Prototipo, Demo, Juego completo..."
              />
            </div>
          )}

          {step === 'generating' && (
            <div className="text-center py-8">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
              <p className="text-gray-600">
                Creando proyecto y generando plan inicial con IA...
              </p>
              <p className="text-sm text-gray-500 mt-2">
                Esto puede tomar unos momentos
              </p>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 p-6 border-t bg-gray-50">
          {step === 'basic' && (
            <>
              <button
                onClick={onClose}
                className="px-4 py-2 text-gray-600 hover:text-gray-800"
                disabled={loading}
              >
                Cancelar
              </button>
              <button
                onClick={handleBasicNext}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                disabled={loading}
              >
                Siguiente
              </button>
            </>
          )}

          {step === 'manifest' && (
            <>
              <button
                onClick={() => setStep('basic')}
                className="px-4 py-2 text-gray-600 hover:text-gray-800"
                disabled={loading}
              >
                Atrás
              </button>
              <button
                onClick={onClose}
                className="px-4 py-2 text-gray-600 hover:text-gray-800"
                disabled={loading}
              >
                Cancelar
              </button>
              <button
                onClick={handleManifestNext}
                className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
                disabled={loading}
              >
                Crear y Generar Plan
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

interface ManifestFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  textarea?: boolean;
  placeholder?: string;
}

function ManifestField({ label, value, onChange, required = false, textarea = false, placeholder }: ManifestFieldProps) {
  return (
    <div>
      <label className="block text-sm font-medium mb-1">
        {label}
        {required && <span className="text-red-500 ml-1">*</span>}
      </label>
      {textarea ? (
        <textarea
          className="w-full border rounded-md px-3 py-2 h-20 text-sm"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
        />
      ) : (
        <input
          type="text"
          className="w-full border rounded-md px-3 py-2 text-sm"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
        />
      )}
    </div>
  );
}