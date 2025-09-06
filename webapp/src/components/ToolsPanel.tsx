export default function ToolsPanel() {
  return (
    <div>
      <div className="font-medium mb-2">Herramientas</div>
      <div className="grid grid-cols-2 gap-2">
        {['Create Primitive', 'Export FBX', 'Instantiate FBX'].map(x => (
          <div key={x} className="border rounded p-2 text-sm">{x}</div>
        ))}
      </div>
    </div>
  )
}

