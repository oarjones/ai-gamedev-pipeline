import { PlanConsensus } from "../components/PlanConsensus";
import { useAppStore } from "../store/appStore";

export default function Consensus() {
    const project_id = useAppStore(s => s.project_id);

    if (!project_id) {
        return <div className="text-center p-8">Please select a project first.</div>;
    }

    return (
        <div>
            <h1 className="text-2xl font-bold mb-4">Plan Consensus</h1>
            <PlanConsensus project_id={project_id} />
        </div>
    );
}