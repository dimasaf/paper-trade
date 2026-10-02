"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Overview" },
  { href: "/tokens", label: "Tokens" },
  { href: "/wallets", label: "Wallets" },
  { href: "/realtime", label: "Realtime" },
  { href: "/clusters", label: "Clusters" },
  { href: "/discovery", label: "Discovery" },
  { href: "/settings", label: "Settings" },
] as const;

export default function SiteNav() {
  const pathname = usePathname();

  return (
    <nav className="mb-8 flex gap-5 text-sm text-cyan-300">
      {links.map((link) => {
        const current =
          link.href === "/"
            ? pathname === "/"
            : pathname === link.href || pathname.startsWith(`${link.href}/`);
        return current ? (
          <span key={link.href} aria-current="page" className="text-white">
            {link.label}
          </span>
        ) : (
          <Link key={link.href} href={link.href}>
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
