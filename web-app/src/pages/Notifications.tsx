import type { NavigateFn } from '../App';
interface Props { navigate: NavigateFn; }
export default function Notifications(_props: Props) {
  return <div className="page page-notifications"><div className="card"><h2>Notifications</h2><p className="text-muted">Coming soon</p></div></div>;
}
