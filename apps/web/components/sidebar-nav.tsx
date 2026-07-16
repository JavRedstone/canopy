"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function SidebarNav() {
  const pathname = usePathname();
  const coursesActive = pathname === "/courses" || (pathname.startsWith("/courses/") && !pathname.startsWith("/courses/new"));

  return (
    <nav className="sidebar-nav">
      <Link href="/courses" className={coursesActive ? "sidebar-nav-active" : undefined}>
        My courses
      </Link>
    </nav>
  );
}
