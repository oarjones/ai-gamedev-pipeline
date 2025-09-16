import { ContextPanel } from "../components/ContextPanel";
import { useAppStore } from "../store/appStore";

export default function Context() {
    const project_id = useAppStore(s => s.project_id);

    if (!project_id) {
        return <div className="text-center p-8">Please select a project first.</div>;
    }

    return (
        <ContextPanel project_id={project_id} />
    );
}