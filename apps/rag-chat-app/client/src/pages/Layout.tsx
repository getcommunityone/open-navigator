import { NavLink, Outlet } from 'react-router';
import { MessagesSquare, BarChart3 } from 'lucide-react';

const TABS = [
  { to: '/', label: 'RAG Chat', icon: MessagesSquare, end: true },
  { to: '/analytics', label: 'NYC Taxi Analytics', icon: BarChart3, end: false },
];

export function Layout() {
  return (
    <div className="flex h-screen flex-col bg-background">
      <nav className="flex items-center gap-1 border-b px-4 py-2">
        <span className="mr-4 text-sm font-semibold text-foreground">Open Navigator · Databricks</span>
        {TABS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm transition-colors ${
                isActive ? 'bg-primary/10 font-medium text-foreground' : 'text-muted-foreground hover:bg-muted'
              }`
            }
          >
            <Icon className="h-4 w-4" />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="min-h-0 flex-1">
        <Outlet />
      </div>
    </div>
  );
}
