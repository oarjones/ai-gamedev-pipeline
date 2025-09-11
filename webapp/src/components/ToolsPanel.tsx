export default function ToolsPanel() {
  const items = [
    { name: 'Create Primitive', desc: 'Crea una primitiva en Blender' },
    { name: 'Export FBX', desc: 'Exporta la escena a FBX' },
    { name: 'Instantiate FBX', desc: 'Instancia un FBX en Unity' },
  ]
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h2 className="font-semibold flex items-center gap-2"><WrenchIcon /> Tools</h2>
      </div>
      <div className="grid grid-cols-2 gap-2">
        {items.map(x => (
          <div key={x.name} className="border rounded p-2 text-sm">
            <div className="font-medium">{x.name}</div>
            <div className="text-xs text-muted-foreground">{x.desc}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function WrenchIcon(){ return (<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M22 19l-6.5-6.5a5 5 0 11-1.5-1.5L20 17.5V19h2zM7 9a3 3 0 100-6 3 3 0 000 6z"/></svg>) }
