import type { NavigateFn } from '../App';
interface Props { navigate: NavigateFn; }
export default function Copilot(_props: Props) {
  return <div className="page page-copilot"><div className="card"><h2>AI Copilot</h2><p className="text-muted">Coming soon</p></div></div>;
}
