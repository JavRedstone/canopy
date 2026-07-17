"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import List from "@mui/material/List";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemText from "@mui/material/ListItemText";

export function SidebarNav() {
  const pathname = usePathname();
  const coursesActive = pathname === "/courses" || (pathname.startsWith("/courses/") && !pathname.startsWith("/courses/new"));

  return (
    <List component="nav" disablePadding sx={{ flex: 1, mt: 0.25 }}>
      <ListItemButton
        component={Link}
        href="/courses"
        selected={coursesActive}
        dense
        sx={{ borderRadius: 1.5, py: 0.75 }}
      >
        <ListItemText slotProps={{ primary: { sx: { fontWeight: 600, fontSize: "0.88rem" } } }}>My courses</ListItemText>
      </ListItemButton>
    </List>
  );
}
