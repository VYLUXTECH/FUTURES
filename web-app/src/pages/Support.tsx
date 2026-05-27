import type { NavigateFn } from '../App';
interface Props { navigate: NavigateFn; }
export default function Support(_props: Props) {
  return <div className="page page-support"><div className="card"><h2>Support</h2><p className="text-muted">Coming soon</p></div></div>;
}
