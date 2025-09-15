import { ContextPanel } from "../components/ContextPanel";
import { useAppStore } from "../store/appStore";

export default function Context() {
    const projectId = useAppStore(s => s.projectId);

    if (!projectId) {
        return <div className="text-center p-8">Please select a project first.</div>;
    }

    return (
        <ContextPanel projectId={projectId} />
    );
}