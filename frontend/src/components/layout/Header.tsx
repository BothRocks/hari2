import { Link, useLocation } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { LoginButton } from '@/components/auth/LoginButton';

export function Header() {
  const location = useLocation();

  const links = [
    { href: '/', label: 'Chat' },
    { href: '/jobs', label: 'Jobs' },
    { href: '/admin', label: 'Admin' },
  ];

  return (
    <header className="border-b">
      <div className="container mx-auto px-4 h-14 flex items-center justify-between">
        <Link to="/" className="font-bold text-xl">HARI</Link>
        <div className="flex items-center gap-6">
          <nav className="flex gap-4">
            {links.map(link => (
              <Link
                key={link.href}
                to={link.href}
                className={cn(
                  "text-sm font-medium transition-colors hover:text-primary",
                  location.pathname === link.href ? "text-primary" : "text-muted-foreground"
                )}
              >
                {link.label}
              </Link>
            ))}
          </nav>
          <LoginButton />
        </div>
      </div>
    </header>
  );
}
